"""Tests for test_algenta_runtime: runtime_api_c.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-3/tests/test_algenta_runtime.py during modularization.
"""
from __future__ import annotations

from tests._test_algenta_runtime_helpers import *  # noqa: F401,F403


def test_runtime_api_mode_get_runtime_benchmarks_rejects_missing_discovered_shipping_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.codna.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    discovery_index = next(
        index
        for index, entry in enumerate(payload["benchmark_discovery_lane"]["discovered_source_inventory"])
        if entry["import_path"] == payload["module_benchmarks"][0]["name"]
    )
    replacement_import_path = f"{payload['module_benchmarks'][0]['name']}_shadow"
    payload["benchmark_discovery_lane"]["discovered_source_inventory"][discovery_index][
        "import_path"
    ] = replacement_import_path

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert (
        exc_info.value.validation_errors[0]["path"]
        == "benchmark_discovery_lane.discovered_source_inventory"
    )
    assert (
        exc_info.value.field_errors[0]["path"]
        == "benchmark_discovery_lane.discovered_source_inventory"
    )


def test_runtime_api_mode_get_runtime_benchmarks_rejects_shipping_benchmark_artifact_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.codna.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_benchmark_artifacts"][0], payload["shipping_runtime_benchmark_artifacts"][1] = (
        payload["shipping_runtime_benchmark_artifacts"][1],
        payload["shipping_runtime_benchmark_artifacts"][0],
    )

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_benchmark_artifacts.0"
    assert exc_info.value.field_errors[0]["path"] == "shipping_runtime_benchmark_artifacts.0"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_shipping_compiled_artifact_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.codna.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_compiled_artifacts"][0] = "build/mismatched-runtime-compiled-artifact.json"

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_compiled_artifacts.0"
    assert exc_info.value.field_errors[0]["path"] == "shipping_runtime_compiled_artifacts.0"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_shipping_compiled_engine_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.codna.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_compiled_engines"][0] = "python_fallback"

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_compiled_engines.0"
    assert exc_info.value.field_errors[0]["path"] == "shipping_runtime_compiled_engines.0"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_invalid_slo_budget_applies_to(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.codna.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["slo_budgets"][0]["applies_to"] = "shadow_realm_lane"

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "slo_budgets.0.applies_to"
    assert exc_info.value.field_errors[0]["path"] == "slo_budgets.0.applies_to"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_invalid_non_shipping_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.codna.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["benchmark_discovery_lane"]["non_shipping_rule"] = "shadow_inventory_lane"

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert (
        exc_info.value.validation_errors[0]["path"]
        == "benchmark_discovery_lane.non_shipping_rule"
    )
    assert (
        exc_info.value.field_errors[0]["path"]
        == "benchmark_discovery_lane.non_shipping_rule"
    )


@pytest.mark.parametrize(
    ("shipping_field", "benchmark_field"),
    [
        ("shipping_runtime_max_cold_ms", "max_cold_ms"),
        ("shipping_runtime_max_warm_ms", "max_warm_ms"),
        ("shipping_runtime_max_hot_ms", "max_hot_ms"),
    ],
)
def test_runtime_api_mode_get_runtime_benchmarks_rejects_shipping_latency_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    shipping_field: str,
    benchmark_field: str,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.codna.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload[shipping_field][0] = payload["module_benchmarks"][0][benchmark_field] + 1.0

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == f"{shipping_field}.0"
    assert exc_info.value.field_errors[0]["path"] == f"{shipping_field}.0"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_duplicate_compiled_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.codna.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["compiled_artifacts"].append(dict(payload["compiled_artifacts"][0]))

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "compiled_artifacts"
    assert exc_info.value.field_errors[0]["path"] == "compiled_artifacts"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_missing_compiled_artifact_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.codna.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["module_benchmarks"][0]["compiled_artifact"] = "build/missing-runtime-benchmark.json"
    payload["shipping_runtime_compiled_artifacts"][0] = "build/missing-runtime-benchmark.json"

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "module_benchmarks.0.compiled_artifact"
    assert exc_info.value.field_errors[0]["path"] == "module_benchmarks.0.compiled_artifact"


def test_runtime_api_mode_get_runtime_release_validation_rejects_duplicate_condition_evidence_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.codna.ai")
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["conditions"][0]["evidence_paths"].append(payload["conditions"][0]["evidence_paths"][0])

    class _FakeClient:
        def get_runtime_release_validation(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_release_validation()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "conditions.0.evidence_paths"
    assert exc_info.value.field_errors[0]["path"] == "conditions.0.evidence_paths"


def test_runtime_api_mode_runtime_proof_surfaces_fail_closed_on_invalid_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import (
        get_runtime_admin_benchmarks,
        get_runtime_admin_modules,
        get_runtime_manifest,
        get_runtime_release_validation,
    )

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.codna.ai")

    invalid_manifest = get_runtime_manifest().model_dump(mode="json")
    invalid_manifest["maturity"]["bpe_tokenizer"] = "legendary"

    invalid_modules = get_runtime_admin_modules().model_dump(mode="json")
    invalid_modules["proof_matrix"][0]["status"] = "unknown_status"

    invalid_benchmarks = get_runtime_admin_benchmarks().model_dump(mode="json")
    invalid_benchmarks["module_benchmarks"][0]["compiled_engine"] = "warp_core"

    invalid_validation = get_runtime_release_validation().model_dump(mode="json")
    invalid_validation["conditions"][0]["condition"] = "teleport-validated"

    class _FakeClient:
        def __init__(self, payload: dict[str, object], method: str) -> None:
            self._payload = payload
            self._method = method

        def get_runtime_manifest(self) -> object:
            if self._method != "manifest":
                raise AssertionError("unexpected manifest call")
            return SimpleNamespace(model_dump=lambda: self._payload)

        def get_runtime_modules(self) -> object:
            if self._method != "modules":
                raise AssertionError("unexpected modules call")
            return SimpleNamespace(model_dump=lambda: self._payload)

        def get_runtime_benchmarks(self) -> object:
            if self._method != "benchmarks":
                raise AssertionError("unexpected benchmarks call")
            return SimpleNamespace(model_dump=lambda: self._payload)

        def get_runtime_release_validation(self) -> object:
            if self._method != "validation":
                raise AssertionError("unexpected validation call")
            return SimpleNamespace(model_dump=lambda: self._payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient(invalid_manifest, "manifest"))
    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as manifest_exc:
        runtime.get_runtime_manifest()
    assert manifest_exc.value.code == "invalid_runtime_contract_payload"

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient(invalid_modules, "modules"))
    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as modules_exc:
        runtime.get_runtime_modules()
    assert modules_exc.value.code == "invalid_runtime_contract_payload"

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient(invalid_benchmarks, "benchmarks"))
    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as benchmarks_exc:
        runtime.get_runtime_benchmarks()
    assert benchmarks_exc.value.code == "invalid_runtime_contract_payload"

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient(invalid_validation, "validation"))
    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as validation_exc:
        runtime.get_runtime_release_validation()
    assert validation_exc.value.code == "invalid_runtime_contract_payload"


def test_runtime_api_mode_real_public_s3_connect_resolve_query(
    runtime_api_client: _AsgiRuntimeApiClient,
) -> None:
    runtime = Runtime(mode="api", api_key="de_test_runtime", base_url="http://test")
    runtime._api_client = runtime_api_client

    imported = runtime.import_preview(
        PUBLIC_S3_CONNECTION,
        name="noaa_hourly",
        source_ref=PUBLIC_S3_SOURCE_REF,
    )
    plan = runtime.resolve(
        {
            "source_name": imported.registration.name,
            "metric": _registration_metric_field(imported.registration),
            "aggregation": "count",
        }
    )
    result = runtime.query(plan)

    assert imported.registration.status == "registered"
    assert imported.registration.row_count is not None
    assert imported.registration.row_count > 0
    assert "Codna Source Import" in imported.preview
    assert f"Origin: {PUBLIC_S3_SOURCE_REF}" in imported.preview
    assert plan.resolved_plan is not None
    assert result.result_type == "scalar"
    assert _result_scalar_value(result.result) == pytest.approx(
        float(imported.registration.row_count)
    )


@pytest.mark.parametrize(
    ("source_descriptor", "expected_name"),
    [
        (
            {
                "type": "postgres",
                "connection_string": "postgresql://analytics:secret@localhost:5432/orders",
                "schema": "public",
                "table": "orders",
            },
            "orders_pg",
        ),
        (
            {
                "type": "mysql",
                "connection_string": "mysql://analytics:secret@localhost:3306/orders",
                "database": "orders",
                "table": "orders",
            },
            "orders_mysql",
        ),
        (
            {
                "type": "s3",
                "bucket": "algenta-public",
                "key": "orders/orders.csv",
                "format": "csv",
            },
            "orders_s3",
        ),
        (
            {
                "type": "rest",
                "base_url": "https://example.com/api",
                "path": "/orders",
                "method": "GET",
            },
            "orders_rest",
        ),
    ],
)
def test_runtime_api_mode_connect_passes_connector_descriptor_through(
    monkeypatch: pytest.MonkeyPatch,
    source_descriptor: dict[str, object],
    expected_name: str,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.codna.ai")
    captured: dict[str, object] = {}

    class _FakeClient:
        def register_source(
            self,
            source: dict[str, object],
            *,
            description: str | None = None,
        ) -> object:
            captured["source"] = source
            captured["description"] = description
            return SimpleNamespace(
                model_dump=lambda: {
                    "source_id": "src_pg_1",
                    "dataset_id": "src_pg_1",
                    "name": expected_name,
                    "status": "ready",
                    "source_schema": {"fields": ["order_id", "revenue"]},
                    "planner_schema_revision": "schema_pg_1",
                    "latency_ms": 3.4,
                    "row_count": 120,
                }
            )

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    registration = runtime.connect(
        source_descriptor,
        name=expected_name,
        description=f"Primary {expected_name} source",
    )

    assert registration.name == expected_name
    assert captured["description"] == f"Primary {expected_name} source"
    normalized_source = captured["source"]
    assert isinstance(normalized_source, dict)
    assert normalized_source["name"] == expected_name
    connection = normalized_source.get("connection")
    assert isinstance(connection, dict)
    if source_descriptor["type"] in {"postgres", "mysql"}:
        assert connection["type"] == "sql"
        assert connection["provider"] == source_descriptor["type"]
        assert connection["connection_string"] == source_descriptor["connection_string"]
        if source_descriptor["type"] == "postgres":
            assert connection["query"] == "SELECT * FROM public.orders"
        else:
            assert connection["query"] == "SELECT * FROM orders"
    elif source_descriptor["type"] == "s3":
        assert connection == {
            "type": "s3",
            "bucket": "algenta-public",
            "key": "orders/orders.csv",
            "file_type": "csv",
        }
    else:
        assert connection["type"] == "rest_api"
        assert connection["url"] == "https://example.com/api/orders"
        assert connection["method"] == "GET"
        assert connection["path"] == "/orders"


def test_runtime_api_mode_connect_recovers_row_count_from_source_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.codna.ai")

    class _FakeClient:
        def register_source(
            self,
            source: dict[str, object],
            *,
            description: str | None = None,
        ) -> object:
            return SimpleNamespace(
                model_dump=lambda: {
                    "source_id": "src_rest_1",
                    "dataset_id": "src_rest_1",
                    "name": source.get("name"),
                    "status": "already_registered",
                    "source_schema": {
                        "source": "weather_stations",
                        "fields": ["id", "properties"],
                        "row_count": 500,
                    },
                    "planner_schema_revision": "schema_rest_1",
                    "latency_ms": 3.6,
                }
            )

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    registration = runtime.connect(
        {
            "type": "rest",
            "base_url": "https://api.weather.gov",
            "path": "/stations",
            "method": "GET",
        },
        name="weather_stations",
    )

    assert registration.status == "already_registered"
    assert registration.row_count == 500


@pytest.mark.parametrize(
    ("source_descriptor", "expected_connection"),
    [
        (
            {
                "type": "postgres",
                "location": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "orders",
                    "schema": "public",
                    "table": "orders",
                },
                "auth": {
                    "credentials": {
                        "user": "analytics",
                        "password": "secret",
                    }
                },
            },
            {
                "type": "sql",
                "provider": "postgres",
                "connection_string": "postgresql://analytics:secret@localhost:5432/orders",
                "schema": "public",
                "table": "orders",
                "query": "SELECT * FROM public.orders",
            },
        ),
        (
            {
                "type": "s3",
                "location": {"bucket": "algenta-public", "key": "orders/orders.csv"},
                "options": {"format": "csv"},
            },
            {
                "type": "s3",
                "bucket": "algenta-public",
                "key": "orders/orders.csv",
                "file_type": "csv",
            },
        ),
        (
            {
                "type": "rest",
                "location": {"base_url": "https://example.com/api", "path": "/orders"},
                "auth": {"mode": "token", "credentials": {"token": "secret-token"}},
                "options": {"method": "GET"},
            },
            {
                "type": "rest_api",
                "url": "https://example.com/api/orders",
                "path": "/orders",
                "method": "GET",
                "headers": {"Authorization": "Bearer secret-token"},
            },
        ),
        (
            {
                "type": "csv",
                "location": {"path": str(REAL_MARCH_ORDERS)},
                "options": {"delimiter": ","},
            },
            {
                "type": "file",
                "file_type": "csv",
                "file_path": str(REAL_MARCH_ORDERS),
                "delimiter": ",",
            },
        ),
    ],
)
def test_runtime_api_mode_accepts_canonical_connector_envelope(
    monkeypatch: pytest.MonkeyPatch,
    source_descriptor: dict[str, object],
    expected_connection: dict[str, object],
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.codna.ai")
    captured: dict[str, object] = {}

    class _FakeClient:
        def register_source(
            self,
            source: dict[str, object],
            *,
            description: str | None = None,
        ) -> object:
            captured["source"] = source
            captured["description"] = description
            return SimpleNamespace(
                model_dump=lambda: {
                    "source_id": "src_1",
                    "dataset_id": "src_1",
                    "name": "canonical_source",
                    "status": "ready",
                    "source_schema": {"fields": ["order_id", "revenue"]},
                    "planner_schema_revision": "schema_1",
                    "latency_ms": 2.1,
                    "row_count": 3,
                }
            )

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    registration = runtime.connect(
        source_descriptor,
        name="canonical_source",
        description="Canonical source",
    )

    assert registration.name == "canonical_source"
    assert captured["description"] == "Canonical source"
    normalized_source = captured["source"]
    assert isinstance(normalized_source, dict)
    assert normalized_source["name"] == "canonical_source"
    assert normalized_source["connection"] == expected_connection


def test_runtime_api_mode_import_bundle_preview_supports_mixed_connector_descriptors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.codna.ai")
    seen: list[dict[str, object]] = []

    class _FakeClient:
        def register_source(
            self,
            source: dict[str, object],
            *,
            description: str | None = None,
        ) -> object:
            seen.append(source)
            connection = source.get("connection")
            if isinstance(connection, dict) and connection.get("type") == "rest_api":
                raise RuntimeValidationError(
                    "upstream_validation_failed",
                    "REST source rejected by hosted connector validation.",
                    {"source": connection.get("url")},
                )
            return SimpleNamespace(
                model_dump=lambda: {
                    "source_id": f"src_{len(seen)}",
                    "dataset_id": f"src_{len(seen)}",
                    "name": source.get("name"),
                    "status": "ready",
                    "source_schema": {"fields": ["order_id", "revenue", "store_name"]},
                    "planner_schema_revision": f"schema_{len(seen)}",
                    "latency_ms": 3.4,
                    "row_count": 120,
                }
            )

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    bundle = runtime.import_bundle_preview(
        [
            {
                "type": "postgres",
                "location": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "orders",
                    "schema": "public",
                    "table": "orders",
                },
                "auth": {
                    "credentials": {
                        "user": "analytics",
                        "password": "secret",
                    }
                },
            },
            {
                "type": "s3",
                "bucket": "algenta-public",
                "key": "orders/orders.csv",
                "format": "csv",
            },
            {
                "type": "rest",
                "base_url": "https://example.com/api",
                "path": "/orders",
                "method": "GET",
            },
        ],
        names=["orders_pg", "orders_s3", "orders_rest"],
        source_refs=[
            "postgres://orders",
            "s3://algenta-public/orders/orders.csv",
            "https://example.com/api/orders",
        ],
    )

    assert len(bundle.registrations) == 2
    assert len(bundle.failures) == 1
    assert bundle.failures[0].code == "upstream_validation_failed"
    assert "Codna Source Bundle" in bundle.preview
    assert "Imported: 2 | Failures: 1" in bundle.preview
    assert "orders_pg" in bundle.preview
    assert "orders_s3" in bundle.preview
    assert "orders_rest: upstream_validation_failed" in bundle.preview
    assert [entry["name"] for entry in seen] == ["orders_pg", "orders_s3", "orders_rest"]
    assert [entry["connection"]["type"] for entry in seen] == ["sql", "s3", "rest_api"]
    assert (
        seen[0]["connection"]["connection_string"]
        == "postgresql://analytics:secret@localhost:5432/orders"
    )


