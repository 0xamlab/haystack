from __future__ import annotations

from apps.api_server.schemas.simulate import (
    BootstrapConfig,
    ObjectiveType,
    SimulateRequestAuto,
    SimulationModel,
)
from apps.api_server.services.simulation_payloads import _build_auto_mojo_payload


def _auto_request(
    *,
    simulation_model: SimulationModel,
    bootstrap_config: BootstrapConfig | None = None,
) -> SimulateRequestAuto:
    return SimulateRequestAuto(
        mode="auto",
        simulation_model=simulation_model,
        runs=500,
        bootstrap_config=bootstrap_config,
        scenario={
            "variables": {
                "revenue": {"low": 80_000, "high": 200_000},
                "cost": {"low": 40_000, "high": 90_000},
            },
            "objective": ObjectiveType.MAXIMIZE_NET_VALUE,
        },
    )


def test_auto_bootstrap_payload_synthesizes_deterministic_history() -> None:
    payload = _build_auto_mojo_payload(_auto_request(simulation_model=SimulationModel.BOOTSTRAP))

    assert payload["engine_type"] == "bootstrap"
    assert "bootstrap_config" in payload
    bootstrap_config = payload["bootstrap_config"]
    assert bootstrap_config["statistic"] == "mean"
    assert bootstrap_config["confidence_level"] == 0.95
    assert len(bootstrap_config["historical_data"]) == 30
    assert bootstrap_config["historical_data"][0] == 40_000.0
    assert bootstrap_config["historical_data"][-1] == 110_000.0
    assert bootstrap_config["historical_data"] == sorted(bootstrap_config["historical_data"])


def test_auto_bootstrap_payload_preserves_explicit_config() -> None:
    explicit_config = BootstrapConfig(
        historical_data=[100.0, 120.0, 140.0],
        statistic="median",
        confidence_level=0.9,
    )

    payload = _build_auto_mojo_payload(
        _auto_request(
            simulation_model=SimulationModel.BOOTSTRAP,
            bootstrap_config=explicit_config,
        )
    )

    assert payload["bootstrap_config"] == explicit_config.model_dump()
