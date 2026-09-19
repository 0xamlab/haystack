# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from .request_common import _strip_none


def _normalize_expert_variable(variable: dict[str, Any]) -> dict[str, Any]:
    if "params" in variable and isinstance(variable["params"], dict):
        params = dict(variable["params"])
    else:
        params = _strip_none(
            {
                "mean": variable.get("mean"),
                "std": variable.get("std") or variable.get("std_dev"),
                "low": variable.get("low"),
                "mode": variable.get("mode"),
                "high": variable.get("high"),
                "value": variable.get("value"),
                "min": variable.get("min"),
                "max": variable.get("max"),
                "p": variable.get("p"),
                "shape": variable.get("shape"),
                "scale": variable.get("scale"),
            }
        )
    return {
        "name": variable.get("name", "value"),
        "distribution": variable.get("distribution", "fixed"),
        "params": params,
    }


def _normalize_simulation_request(payload: dict[str, Any]) -> dict[str, Any]:
    if "scenario" in payload:
        scenario = payload.get("scenario")
        if isinstance(scenario, dict) and isinstance(scenario.get("variables"), dict):
            normalized_payload = dict(payload)
            normalized_scenario = dict(scenario)
            normalized_scenario.setdefault("objective", "maximize_net_value")
            normalized_payload["scenario"] = normalized_scenario
            return normalized_payload
        return payload

    if "simulation" in payload:
        return payload

    variables = payload.get("variables")
    if isinstance(variables, dict):
        normalized = {
            "mode": "auto",
            "scenario": {
                "variables": variables,
                "objective": payload.get("objective", "maximize_net_value"),
            },
            "runs": payload.get("runs", 10_000),
        }
        if payload.get("seed") is not None:
            normalized["seed"] = payload["seed"]
        if payload.get("simulation_model") is not None:
            normalized["simulation_model"] = payload["simulation_model"]
        return normalized

    if isinstance(variables, list):
        variable_names = [v.get("name", "value") for v in variables if isinstance(v, dict)]
        objective = (
            payload.get("objective_function")
            or payload.get("objective")
            or " + ".join(variable_names)
            or "value"
        )
        normalized = {
            "mode": "expert",
            "simulation": {
                "variables": [
                    _normalize_expert_variable(v) for v in variables if isinstance(v, dict)
                ],
                "objective_function": objective,
                "scoring": payload.get("scoring", {"expected_value": 0.6, "downside_risk": 0.4}),
            },
            "runs": payload.get("runs", 10_000),
        }
        if payload.get("seed") is not None:
            normalized["seed"] = payload["seed"]
        if payload.get("simulation_model") is not None:
            normalized["simulation_model"] = payload["simulation_model"]
        return normalized

    return payload


def _normalize_recommend_request(actions: Any, **kwargs: Any) -> dict[str, Any]:
    if isinstance(actions, dict):
        payload = dict(actions)
        if "actions" in payload:
            return payload
        if "options" in payload:
            normalized_actions = []
            for idx, option in enumerate(payload.get("options", []), start=1):
                name = option.get("label") or option.get("name") or f"option_{idx}"
                expected_value = float(option.get("expected_value", 0.0) or 0.0)
                risk = max(float(option.get("risk", 0.1) or 0.1), 0.05)
                spread = max(abs(expected_value) * risk, 1.0)
                normalized_actions.append(
                    {
                        "name": name,
                        "request": {
                            "mode": "expert",
                            "simulation": {
                                "variables": [
                                    {
                                        "name": "outcome",
                                        "distribution": "triangular",
                                        "params": {
                                            "low": expected_value - spread,
                                            "mode": expected_value,
                                            "high": expected_value + spread,
                                        },
                                    }
                                ],
                                "objective_function": "outcome",
                                "scoring": {"expected_value": 0.6, "downside_risk": 0.4},
                            },
                            "runs": payload.get("runs", 1000),
                        },
                    }
                )
            return {"actions": normalized_actions, "runs": payload.get("runs", 1000)}
        return payload

    return {"actions": actions, **kwargs}


def _normalize_compare_request(scenarios: Any, **kwargs: Any) -> dict[str, Any]:
    if isinstance(scenarios, dict):
        payload = dict(scenarios)
        if "scenarios" in payload:
            scenarios = payload["scenarios"]
            kwargs = {key: value for key, value in payload.items() if key != "scenarios"}
        else:
            return payload

    normalized = []
    for idx, scenario in enumerate(scenarios, start=1):
        if isinstance(scenario, dict) and "request" in scenario and "name" in scenario:
            normalized.append(scenario)
            continue
        if isinstance(scenario, dict):
            name = scenario.get("label") or scenario.get("name") or f"scenario_{idx}"
            request = _normalize_simulation_request(
                {key: value for key, value in scenario.items() if key not in {"label", "name"}}
            )
            normalized.append({"name": name, "request": request})
    return {"scenarios": normalized, **kwargs}


__all__ = [
    "_normalize_compare_request",
    "_normalize_expert_variable",
    "_normalize_recommend_request",
    "_normalize_simulation_request",
]
