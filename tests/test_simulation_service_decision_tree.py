from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException

from apps.api_server.schemas.simulate import SimulateRequestExpert
from apps.api_server.services import simulation_service


def _decision_tree_request() -> SimulateRequestExpert:
    return SimulateRequestExpert.model_validate(
        {
            "mode": "expert",
            "simulation_model": "decision_tree",
            "runs": 100,
            "seed": 7,
            "simulation": {
                "variables": [
                    {
                        "name": "revenue",
                        "distribution": "normal",
                        "params": {"mean": 120_000.0, "std": 15_000.0},
                    },
                    {
                        "name": "cost",
                        "distribution": "normal",
                        "params": {"mean": 70_000.0, "std": 10_000.0},
                    },
                ],
                "objective_function": "revenue - cost",
                "scoring": {"expected_value": 0.6, "downside_risk": 0.4},
            },
            "decision_tree_config": {
                "nodes": [
                    {
                        "id": "launch",
                        "type": "decision",
                        "name": "Launch?",
                        "branches": [
                            {
                                "id": "market_accepts",
                                "type": "terminal",
                                "name": "Market Accepts",
                                "probability": 0.65,
                            },
                            {
                                "id": "market_rejects",
                                "type": "terminal",
                                "name": "Market Rejects",
                                "probability": 0.35,
                                "variables": {"revenue": 0.0},
                                "objective_function": "-cost",
                            },
                        ],
                    }
                ],
                "max_depth": 4,
            },
        }
    )


def test_build_expert_mojo_payload_flattens_decision_tree_nodes_to_paths() -> None:
    request = _decision_tree_request()

    payload = simulation_service._build_expert_mojo_payload(request)

    decision_tree_config = payload["decision_tree_config"]
    assert "paths" in decision_tree_config
    assert "nodes" not in decision_tree_config
    assert len(decision_tree_config["paths"]) == 2

    paths_by_label = {path["label"]: path for path in decision_tree_config["paths"]}
    accepts = paths_by_label["Launch? > Market Accepts"]
    rejects = paths_by_label["Launch? > Market Rejects"]

    assert accepts["objective_function"] == "revenue - cost"
    assert pytest.approx(accepts["probability"], rel=1e-9) == 0.65
    assert rejects["objective_function"] == "-cost"
    assert pytest.approx(rejects["probability"], rel=1e-9) == 0.35

    reject_variables = {variable["name"]: variable for variable in rejects["variables"]}
    assert reject_variables["revenue"]["distribution"] == "fixed"
    assert reject_variables["revenue"]["params"]["value"] == 0.0
    assert reject_variables["cost"]["distribution"] == "normal"


def test_build_expert_mojo_payload_rejects_invalid_decision_tree_override() -> None:
    request = SimulateRequestExpert.model_validate(
        {
            "mode": "expert",
            "simulation_model": "decision_tree",
            "runs": 100,
            "simulation": {
                "variables": [
                    {
                        "name": "revenue",
                        "distribution": "normal",
                        "params": {"mean": 120_000.0, "std": 15_000.0},
                    }
                ],
                "objective_function": "revenue",
            },
            "decision_tree_config": {
                "nodes": [
                    {
                        "id": "launch",
                        "name": "Launch?",
                        "branches": [
                            {
                                "id": "bad_branch",
                                "name": "Bad Branch",
                                "probability": 1.0,
                                "variables": {"revenue": {"distribution": "fixed"}},
                            }
                        ],
                    }
                ]
            },
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        simulation_service._build_expert_mojo_payload(request)

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["error"]["code"] == "invalid_decision_tree_override"


@pytest.mark.asyncio
async def test_run_simulation_fast_supports_decision_tree_nodes_payload() -> None:
    if not (Path.cwd() / "mojo_build" / "simulate").exists():
        pytest.skip("mojo_build/simulate binary not available")

    request = _decision_tree_request()

    envelope, persist_meta = await simulation_service.run_simulation_fast(
        request=request,
        org_id=uuid.uuid4(),
        api_key_id=uuid.uuid4(),
    )

    assert envelope.simulation_model == "decision_tree"
    assert envelope.decision_tree_result is not None
    assert envelope.decision_tree_result["n_paths"] == 2
    assert len(envelope.decision_tree_result["paths"]) == 2
    assert persist_meta["simulation_model"] == "decision_tree"
