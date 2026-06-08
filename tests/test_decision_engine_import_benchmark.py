from __future__ import annotations

import json

from benchmarks.decision_engine_import_benchmark import _sample_export_resolution, run_benchmark


def test_decision_engine_import_benchmark_reports_expected_shape(monkeypatch) -> None:
    samples = iter([8.0, 9.0, 10.0, 11.0])
    monkeypatch.setattr(
        "benchmarks.decision_engine_import_benchmark._sample_import_ms",
        lambda *, iterations: [next(samples) for _ in range(iterations)],
    )
    monkeypatch.setattr(
        "benchmarks.decision_engine_import_benchmark._sample_export_resolution",
        lambda *, export_name, iterations, preload_modules=(): [
            {
                "elapsed_ms": (
                    15.0
                    if export_name == "DecisionEnvelope"
                    else 18.0
                    if export_name == "QueryResult"
                    else 20.0
                    if export_name == "ConnectorInfo"
                    else 30.0
                    if export_name == "AsyncDecisionEngineClient"
                    else 40.0
                ),
                "loaded_client": False,
                "loaded_async_client": False,
                "loaded_client_facade": export_name == "DecisionEngineClient",
                "loaded_async_client_facade": export_name == "AsyncDecisionEngineClient",
                "loaded_models": export_name
                in {
                    "DecisionEnvelope",
                    "QueryResult",
                    "ConnectorInfo",
                },
                "loaded_model_modules": (
                    [
                        "decision_engine.models_decision_envelope",
                        "decision_engine.models_simulation_common",
                    ]
                    if export_name == "DecisionEnvelope"
                    else ["decision_engine.models_query_result"]
                    if export_name == "QueryResult"
                    else ["decision_engine.models_connector_info"]
                    if export_name == "ConnectorInfo"
                    else []
                ),
                "loaded_connector_surfaces": False,
                "loaded_connector_surface_modules": [],
                "loaded_service_surfaces": False,
                "loaded_service_surface_modules": [],
                "loaded_request_helpers": False,
                "loaded_request_helper_modules": [],
                "loaded_exceptions": False,
                "loaded_httpx": False,
            }
            for _ in range(iterations)
        ],
    )

    results = run_benchmark(iterations=4)

    assert results["iterations"] == 4
    assert results["mean_ms"] == 9.5
    assert results["min_ms"] == 8.0
    assert results["max_ms"] == 11.0
    assert results["exports"]["DecisionEnvelope"]["mean_ms"] == 15.0
    assert results["exports"]["DecisionEnvelope"]["loads_client"] is False
    assert results["exports"]["DecisionEnvelope"]["loads_async_client"] is False
    assert results["exports"]["DecisionEnvelope"]["loads_client_facade"] is False
    assert results["exports"]["DecisionEnvelope"]["loads_async_client_facade"] is False
    assert results["exports"]["DecisionEnvelope"]["loads_models"] is True
    assert results["exports"]["DecisionEnvelope"]["model_modules"] == [
        "decision_engine.models_decision_envelope",
        "decision_engine.models_simulation_common",
    ]
    assert results["exports"]["DecisionEnvelope"]["loads_connector_surfaces"] is False
    assert results["exports"]["DecisionEnvelope"]["connector_surface_modules"] == []
    assert results["exports"]["DecisionEnvelope"]["loads_service_surfaces"] is False
    assert results["exports"]["DecisionEnvelope"]["service_surface_modules"] == []
    assert results["exports"]["DecisionEnvelope"]["loads_request_helpers"] is False
    assert results["exports"]["DecisionEnvelope"]["request_helper_modules"] == []
    assert results["exports"]["DecisionEnvelope"]["loads_httpx"] is False
    assert results["exports"]["DecisionEnvelope"]["pydantic_preloaded"]["mean_ms"] == 15.0
    assert results["exports"]["QueryResult"]["mean_ms"] == 18.0
    assert results["exports"]["QueryResult"]["loads_client"] is False
    assert results["exports"]["QueryResult"]["loads_async_client"] is False
    assert results["exports"]["QueryResult"]["loads_client_facade"] is False
    assert results["exports"]["QueryResult"]["loads_async_client_facade"] is False
    assert results["exports"]["QueryResult"]["loads_models"] is True
    assert results["exports"]["QueryResult"]["model_modules"] == [
        "decision_engine.models_query_result"
    ]
    assert results["exports"]["QueryResult"]["loads_connector_surfaces"] is False
    assert results["exports"]["QueryResult"]["connector_surface_modules"] == []
    assert results["exports"]["QueryResult"]["loads_service_surfaces"] is False
    assert results["exports"]["QueryResult"]["service_surface_modules"] == []
    assert results["exports"]["QueryResult"]["loads_request_helpers"] is False
    assert results["exports"]["QueryResult"]["request_helper_modules"] == []
    assert results["exports"]["QueryResult"]["loads_httpx"] is False
    assert results["exports"]["QueryResult"]["pydantic_preloaded"]["mean_ms"] == 18.0
    assert results["exports"]["ConnectorInfo"]["mean_ms"] == 20.0
    assert results["exports"]["ConnectorInfo"]["loads_client"] is False
    assert results["exports"]["ConnectorInfo"]["loads_async_client"] is False
    assert results["exports"]["ConnectorInfo"]["loads_client_facade"] is False
    assert results["exports"]["ConnectorInfo"]["loads_async_client_facade"] is False
    assert results["exports"]["ConnectorInfo"]["loads_models"] is True
    assert results["exports"]["ConnectorInfo"]["model_modules"] == [
        "decision_engine.models_connector_info"
    ]
    assert results["exports"]["ConnectorInfo"]["loads_connector_surfaces"] is False
    assert results["exports"]["ConnectorInfo"]["connector_surface_modules"] == []
    assert results["exports"]["ConnectorInfo"]["loads_service_surfaces"] is False
    assert results["exports"]["ConnectorInfo"]["service_surface_modules"] == []
    assert results["exports"]["ConnectorInfo"]["loads_request_helpers"] is False
    assert results["exports"]["ConnectorInfo"]["request_helper_modules"] == []
    assert results["exports"]["ConnectorInfo"]["loads_httpx"] is False
    assert results["exports"]["ConnectorInfo"]["pydantic_preloaded"]["mean_ms"] == 20.0
    assert results["exports"]["AsyncDecisionEngineClient"]["mean_ms"] == 30.0
    assert results["exports"]["AsyncDecisionEngineClient"]["loads_async_client"] is False
    assert results["exports"]["AsyncDecisionEngineClient"]["loads_client"] is False
    assert results["exports"]["AsyncDecisionEngineClient"]["loads_async_client_facade"] is True
    assert results["exports"]["AsyncDecisionEngineClient"]["loads_client_facade"] is False
    assert results["exports"]["AsyncDecisionEngineClient"]["loads_models"] is False
    assert results["exports"]["AsyncDecisionEngineClient"]["model_modules"] == []
    assert results["exports"]["AsyncDecisionEngineClient"]["loads_connector_surfaces"] is False
    assert results["exports"]["AsyncDecisionEngineClient"]["connector_surface_modules"] == []
    assert results["exports"]["AsyncDecisionEngineClient"]["loads_service_surfaces"] is False
    assert results["exports"]["AsyncDecisionEngineClient"]["service_surface_modules"] == []
    assert results["exports"]["AsyncDecisionEngineClient"]["loads_request_helpers"] is False
    assert results["exports"]["AsyncDecisionEngineClient"]["request_helper_modules"] == []
    assert results["exports"]["AsyncDecisionEngineClient"]["loads_exceptions"] is False
    assert results["exports"]["AsyncDecisionEngineClient"]["loads_httpx"] is False
    assert results["exports"]["DecisionEngineClient"]["mean_ms"] == 40.0
    assert results["exports"]["DecisionEngineClient"]["loads_client"] is False
    assert results["exports"]["DecisionEngineClient"]["loads_client_facade"] is True
    assert results["exports"]["DecisionEngineClient"]["loads_async_client_facade"] is False
    assert results["exports"]["DecisionEngineClient"]["loads_models"] is False
    assert results["exports"]["DecisionEngineClient"]["model_modules"] == []
    assert results["exports"]["DecisionEngineClient"]["loads_connector_surfaces"] is False
    assert results["exports"]["DecisionEngineClient"]["connector_surface_modules"] == []
    assert results["exports"]["DecisionEngineClient"]["loads_service_surfaces"] is False
    assert results["exports"]["DecisionEngineClient"]["service_surface_modules"] == []
    assert results["exports"]["DecisionEngineClient"]["loads_request_helpers"] is False
    assert results["exports"]["DecisionEngineClient"]["request_helper_modules"] == []
    assert results["exports"]["DecisionEngineClient"]["loads_exceptions"] is False
    assert results["exports"]["DecisionEngineClient"]["loads_httpx"] is False


def test_decision_engine_import_benchmark_formats_export_snippet_with_connector_surface_tracking(
    monkeypatch,
) -> None:
    expected = {
        "elapsed_ms": 5.0,
        "loaded_client": False,
        "loaded_async_client": False,
        "loaded_client_facade": True,
        "loaded_async_client_facade": False,
        "loaded_models": False,
        "loaded_model_modules": [],
        "loaded_connector_surfaces": False,
        "loaded_connector_surface_modules": [],
        "loaded_service_surfaces": False,
        "loaded_service_surface_modules": [],
        "loaded_request_helpers": False,
        "loaded_request_helper_modules": [],
        "loaded_exceptions": False,
        "loaded_httpx": False,
    }

    monkeypatch.setattr(
        "benchmarks.decision_engine_import_benchmark.subprocess.check_output",
        lambda *args, **kwargs: json.dumps(expected),
    )

    samples = _sample_export_resolution(
        export_name="DecisionEngineClient",
        iterations=1,
        preload_modules=("pydantic",),
    )

    assert samples == [expected]
