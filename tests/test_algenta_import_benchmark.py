from __future__ import annotations

import json

from benchmarks.algenta_import_benchmark import _sample_export_resolution, run_benchmark


def test_algenta_import_benchmark_reports_expected_shape(monkeypatch) -> None:
    samples = iter([10.0, 12.0, 11.0, 13.0])
    monkeypatch.setattr(
        "benchmarks.algenta_import_benchmark._sample_import_ms",
        lambda *, iterations: [next(samples) for _ in range(iterations)],
    )
    monkeypatch.setattr(
        "benchmarks.algenta_import_benchmark._sample_export_resolution",
        lambda *, export_name, iterations: [
            {
                "elapsed_ms": (
                    20.0
                    if export_name == "QueryOutput"
                    else 25.0
                    if export_name == "ConnectorMetadata"
                    else 30.0
                    if export_name == "map_data"
                    else 35.0
                    if export_name == "libraries"
                    else 37.0
                    if export_name == "MojoRuntime"
                    else 40.0
                ),
                "loaded_runtime": export_name == "Runtime",
                "loaded_runtime_modules": (
                    ["algenta.runtime_facade"] if export_name == "Runtime" else []
                ),
                "loaded_runtime_errors": export_name == "Runtime",
                "loaded_runtime_model_modules": (
                    ["algenta.runtime_model_query_output"] if export_name == "QueryOutput" else []
                ),
                "loaded_runtime_support_modules": [],
                "loaded_map": export_name == "map_data",
                "loaded_connector_modules": (
                    [
                        "algenta.runtime_connector_model_common",
                        "algenta.runtime_connector_model_metadata",
                    ]
                    if export_name == "ConnectorMetadata"
                    else []
                ),
                "loaded_map_modules": (
                    ["algenta.map_matching"] if export_name == "map_data" else []
                ),
                "loaded_mojo_modules": (
                    ["algenta.mojo_entrypoints"]
                    if export_name == "libraries"
                    else ["algenta.mojo_runtime"]
                    if export_name == "MojoRuntime"
                    else []
                ),
            }
            for _ in range(iterations)
        ],
    )

    results = run_benchmark(iterations=4)

    assert results["iterations"] == 4
    assert results["mean_ms"] == 11.5
    assert results["min_ms"] == 10.0
    assert results["max_ms"] == 13.0
    assert results["p90_ms"] >= 0.0
    assert results["p95_ms"] >= 0.0
    assert results["exports"]["QueryOutput"]["mean_ms"] == 20.0
    assert results["exports"]["QueryOutput"]["loads_runtime"] is False
    assert results["exports"]["QueryOutput"]["runtime_modules"] == []
    assert results["exports"]["QueryOutput"]["loads_runtime_models"] is True
    assert results["exports"]["QueryOutput"]["loads_runtime_errors"] is False
    assert results["exports"]["QueryOutput"]["runtime_model_modules"] == [
        "algenta.runtime_model_query_output"
    ]
    assert results["exports"]["QueryOutput"]["runtime_support_modules"] == []
    assert results["exports"]["QueryOutput"]["loads_map"] is False
    assert results["exports"]["QueryOutput"]["connector_modules"] == []
    assert results["exports"]["QueryOutput"]["map_modules"] == []
    assert results["exports"]["QueryOutput"]["mojo_modules"] == []
    assert results["exports"]["ConnectorMetadata"]["mean_ms"] == 25.0
    assert results["exports"]["ConnectorMetadata"]["loads_runtime"] is False
    assert results["exports"]["ConnectorMetadata"]["runtime_modules"] == []
    assert results["exports"]["ConnectorMetadata"]["loads_runtime_models"] is False
    assert results["exports"]["ConnectorMetadata"]["runtime_model_modules"] == []
    assert results["exports"]["ConnectorMetadata"]["runtime_support_modules"] == []
    assert results["exports"]["ConnectorMetadata"]["loads_map"] is False
    assert results["exports"]["ConnectorMetadata"]["connector_modules"] == [
        "algenta.runtime_connector_model_common",
        "algenta.runtime_connector_model_metadata",
    ]
    assert results["exports"]["ConnectorMetadata"]["map_modules"] == []
    assert results["exports"]["ConnectorMetadata"]["mojo_modules"] == []
    assert results["exports"]["map_data"]["mean_ms"] == 30.0
    assert results["exports"]["map_data"]["loads_runtime"] is False
    assert results["exports"]["map_data"]["runtime_modules"] == []
    assert results["exports"]["map_data"]["loads_runtime_models"] is False
    assert results["exports"]["map_data"]["runtime_model_modules"] == []
    assert results["exports"]["map_data"]["runtime_support_modules"] == []
    assert results["exports"]["map_data"]["loads_map"] is True
    assert results["exports"]["map_data"]["connector_modules"] == []
    assert results["exports"]["map_data"]["map_modules"] == ["algenta.map_matching"]
    assert results["exports"]["map_data"]["mojo_modules"] == []
    assert results["exports"]["Runtime"]["mean_ms"] == 40.0
    assert results["exports"]["Runtime"]["loads_runtime"] is True
    assert results["exports"]["Runtime"]["runtime_modules"] == ["algenta.runtime_facade"]
    assert results["exports"]["Runtime"]["loads_runtime_models"] is False
    assert results["exports"]["Runtime"]["loads_runtime_errors"] is True
    assert results["exports"]["Runtime"]["runtime_model_modules"] == []
    assert results["exports"]["Runtime"]["runtime_support_modules"] == []
    assert results["exports"]["Runtime"]["loads_map"] is False
    assert results["exports"]["Runtime"]["connector_modules"] == []
    assert results["exports"]["Runtime"]["map_modules"] == []
    assert results["exports"]["Runtime"]["mojo_modules"] == []
    assert results["exports"]["libraries"]["mean_ms"] == 35.0
    assert results["exports"]["libraries"]["loads_runtime"] is False
    assert results["exports"]["libraries"]["runtime_modules"] == []
    assert results["exports"]["libraries"]["loads_runtime_models"] is False
    assert results["exports"]["libraries"]["loads_runtime_errors"] is False
    assert results["exports"]["libraries"]["runtime_model_modules"] == []
    assert results["exports"]["libraries"]["runtime_support_modules"] == []
    assert results["exports"]["libraries"]["loads_map"] is False
    assert results["exports"]["libraries"]["connector_modules"] == []
    assert results["exports"]["libraries"]["map_modules"] == []
    assert results["exports"]["libraries"]["mojo_modules"] == ["algenta.mojo_entrypoints"]
    assert results["exports"]["MojoRuntime"]["mean_ms"] == 37.0
    assert results["exports"]["MojoRuntime"]["loads_runtime"] is False
    assert results["exports"]["MojoRuntime"]["runtime_modules"] == []
    assert results["exports"]["MojoRuntime"]["loads_runtime_models"] is False
    assert results["exports"]["MojoRuntime"]["loads_runtime_errors"] is False
    assert results["exports"]["MojoRuntime"]["runtime_model_modules"] == []
    assert results["exports"]["MojoRuntime"]["runtime_support_modules"] == []
    assert results["exports"]["MojoRuntime"]["loads_map"] is False
    assert results["exports"]["MojoRuntime"]["connector_modules"] == []
    assert results["exports"]["MojoRuntime"]["map_modules"] == []
    assert results["exports"]["MojoRuntime"]["mojo_modules"] == ["algenta.mojo_runtime"]


def test_algenta_import_benchmark_formats_export_snippet_with_runtime_support_tracking(
    monkeypatch,
) -> None:
    expected = {
        "elapsed_ms": 5.0,
        "loaded_runtime": True,
        "loaded_runtime_modules": ["algenta.runtime_facade"],
        "loaded_runtime_errors": True,
        "loaded_runtime_model_modules": [],
        "loaded_runtime_support_modules": [],
        "loaded_map": False,
        "loaded_connector_modules": [],
        "loaded_map_modules": [],
        "loaded_mojo_modules": [],
    }

    monkeypatch.setattr(
        "benchmarks.algenta_import_benchmark.subprocess.check_output",
        lambda *args, **kwargs: json.dumps(expected),
    )

    samples = _sample_export_resolution(export_name="Runtime", iterations=1)

    assert samples == [expected]
