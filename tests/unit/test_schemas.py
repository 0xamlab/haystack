"""Unit tests for Pydantic request/response schemas."""

import os
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from apps.api_server.schemas.simulate import (
    AutoVariable,
    ScoringWeights,
    SimulateRequestAuto,
    SimulateRequestExpert,
)


class TestAutoVariable:
    def test_valid_auto_variable(self) -> None:
        v = AutoVariable(low=100.0, high=200.0)
        assert v.low == 100.0
        assert v.high == 200.0

    def test_high_must_exceed_low(self) -> None:
        with pytest.raises(ValidationError, match="high.*must be greater than.*low"):
            AutoVariable(low=200.0, high=100.0)

    def test_equal_low_high_invalid(self) -> None:
        with pytest.raises(ValidationError):
            AutoVariable(low=100.0, high=100.0)


class TestSimulateRequestAuto:
    def test_valid_auto_request(self) -> None:
        req = SimulateRequestAuto.model_validate(
            {
                "mode": "auto",
                "scenario": {
                    "variables": {
                        "revenue": {"low": 80000, "high": 200000},
                        "cost": {"low": 40000, "high": 90000},
                    },
                    "objective": "maximize_net_value",
                },
            }
        )
        assert req.mode == "auto"
        assert req.runs == 10000  # default
        assert req.seed is None  # default

    def test_missing_scenario_invalid(self) -> None:
        with pytest.raises(ValidationError):
            SimulateRequestAuto.model_validate({"mode": "auto"})

    def test_runs_below_minimum(self) -> None:
        with pytest.raises(ValidationError):
            SimulateRequestAuto.model_validate(
                {
                    "mode": "auto",
                    "scenario": {
                        "variables": {"x": {"low": 1, "high": 10}},
                        "objective": "maximize_net_value",
                    },
                    "runs": 50,  # below minimum of 100
                }
            )

    def test_runs_above_maximum(self) -> None:
        with pytest.raises(ValidationError):
            SimulateRequestAuto.model_validate(
                {
                    "mode": "auto",
                    "scenario": {
                        "variables": {"x": {"low": 1, "high": 10}},
                        "objective": "maximize_net_value",
                    },
                    "runs": 200000,  # above maximum of 100000 for auto mode
                }
            )

    def test_custom_seed_accepted(self) -> None:
        req = SimulateRequestAuto.model_validate(
            {
                "mode": "auto",
                "scenario": {
                    "variables": {"x": {"low": 1, "high": 10}},
                    "objective": "maximize_net_value",
                },
                "seed": 42,
            }
        )
        assert req.seed == 42


class TestSimulateRequestExpert:
    def test_valid_normal_distribution(self) -> None:
        req = SimulateRequestExpert.model_validate(
            {
                "mode": "expert",
                "simulation": {
                    "variables": [
                        {
                            "name": "revenue",
                            "distribution": "normal",
                            "params": {"mean": 100000, "std": 20000},
                        }
                    ],
                },
            }
        )
        assert req.mode == "expert"
        assert len(req.simulation.variables) == 1

    def test_normal_missing_std(self) -> None:
        with pytest.raises(ValidationError, match="requires.*std"):
            SimulateRequestExpert.model_validate(
                {
                    "mode": "expert",
                    "simulation": {
                        "variables": [
                            {
                                "name": "revenue",
                                "distribution": "normal",
                                "params": {"mean": 100000},
                            }
                        ],
                    },
                }
            )

    def test_triangular_invalid_mode(self) -> None:
        """Mode must satisfy low <= mode <= high."""
        with pytest.raises(ValidationError, match="low.*<=.*mode.*<=.*high"):
            SimulateRequestExpert.model_validate(
                {
                    "mode": "expert",
                    "simulation": {
                        "variables": [
                            {
                                "name": "x",
                                "distribution": "triangular",
                                "params": {"low": 100, "mode": 50, "high": 200},  # mode < low
                            }
                        ],
                    },
                }
            )

    def test_uniform_invalid_bounds(self) -> None:
        with pytest.raises(ValidationError, match="high.*must exceed.*low"):
            SimulateRequestExpert.model_validate(
                {
                    "mode": "expert",
                    "simulation": {
                        "variables": [
                            {
                                "name": "x",
                                "distribution": "uniform",
                                "params": {"low": 100, "high": 50},
                            }
                        ],
                    },
                }
            )

    def test_fixed_distribution(self) -> None:
        req = SimulateRequestExpert.model_validate(
            {
                "mode": "expert",
                "simulation": {
                    "variables": [
                        {
                            "name": "cost",
                            "distribution": "fixed",
                            "params": {"value": 50000},
                        }
                    ],
                },
            }
        )
        assert req.simulation.variables[0].distribution.value == "fixed"

    def test_runs_above_expert_maximum(self) -> None:
        with pytest.raises(ValidationError):
            SimulateRequestExpert.model_validate(
                {
                    "mode": "expert",
                    "simulation": {
                        "variables": [
                            {"name": "x", "distribution": "fixed", "params": {"value": 1}},
                        ],
                    },
                    "runs": 2_000_000,  # above 1,000,000
                }
            )


class TestScoringWeights:
    def test_valid_weights(self) -> None:
        w = ScoringWeights(expected_value=0.7, downside_risk=0.3)
        assert w.expected_value == 0.7

    def test_weights_must_sum_to_one(self) -> None:
        with pytest.raises(ValidationError, match="sum to 1.0"):
            ScoringWeights(expected_value=0.6, downside_risk=0.6)

    def test_default_weights_valid(self) -> None:
        w = ScoringWeights()
        total = w.expected_value + w.downside_risk
        assert abs(total - 1.0) < 0.001
