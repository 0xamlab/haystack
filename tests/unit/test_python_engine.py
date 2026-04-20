"""
Unit tests for the Python reference simulation engine (mojo/bindings/python_adapter.py).
These tests validate simulation math, determinism, and output schema correctness.
"""
import os
import sys

import pytest

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

run_simulation = pytest.importorskip(
    "mojo.bindings.python_adapter", reason="Mojo engine not available"
).run_simulation

# ─── Test fixtures ─────────────────────────────────────────────────────────────

NORMAL_PAYLOAD = {
    "runs": 10000,
    "seed": 42,
    "variables": [
        {"name": "revenue", "distribution": "normal", "params": {"mean": 100000, "std": 20000}}
    ],
    "objective_function": "revenue",
}

TRIANGULAR_PAYLOAD = {
    "runs": 10000,
    "seed": 42,
    "variables": [
        {"name": "revenue", "distribution": "triangular", "params": {"low": 50000, "mode": 100000, "high": 200000}},
        {"name": "cost", "distribution": "uniform", "params": {"low": 30000, "high": 80000}},
    ],
    "objective_function": "revenue - cost",
}


# ─── Determinism ───────────────────────────────────────────────────────────────

class TestDeterminism:
    def test_same_seed_produces_identical_results(self) -> None:
        """Critical: same seed must always produce the exact same output."""
        result_1 = run_simulation(NORMAL_PAYLOAD)
        result_2 = run_simulation(NORMAL_PAYLOAD)
        assert result_1["summary"]["mean"] == result_2["summary"]["mean"]
        assert result_1["summary"]["std"] == result_2["summary"]["std"]
        assert result_1["percentiles"]["p50"] == result_2["percentiles"]["p50"]

    def test_different_seeds_produce_different_results(self) -> None:
        """Different seeds should produce different (statistically) results."""
        payload_1 = {**NORMAL_PAYLOAD, "seed": 1}
        payload_2 = {**NORMAL_PAYLOAD, "seed": 999}
        result_1 = run_simulation(payload_1)
        result_2 = run_simulation(payload_2)
        # Very unlikely to be identical with different seeds and 10k runs
        assert result_1["summary"]["mean"] != result_2["summary"]["mean"]

    def test_null_seed_runs_without_error(self) -> None:
        """None seed (unseeded) should still produce valid output."""
        payload = {**NORMAL_PAYLOAD, "seed": None}
        result = run_simulation(payload)
        assert result["scenarios_run"] == 10000
        assert "summary" in result


# ─── Output Schema ─────────────────────────────────────────────────────────────

class TestOutputSchema:
    def test_required_fields_present(self) -> None:
        result = run_simulation(NORMAL_PAYLOAD)
        assert "engine_version" in result
        assert "scenarios_run" in result
        assert "summary" in result
        assert "percentiles" in result
        assert "risk" in result

    def test_summary_fields(self) -> None:
        result = run_simulation(NORMAL_PAYLOAD)
        summary = result["summary"]
        assert "mean" in summary
        assert "median" in summary
        assert "std" in summary
        assert "variance" in summary

    def test_percentile_fields(self) -> None:
        result = run_simulation(NORMAL_PAYLOAD)
        p = result["percentiles"]
        assert "p5" in p
        assert "p25" in p
        assert "p50" in p
        assert "p75" in p
        assert "p95" in p

    def test_percentile_ordering(self) -> None:
        """Percentiles must be in ascending order."""
        result = run_simulation(NORMAL_PAYLOAD)
        p = result["percentiles"]
        assert p["p5"] <= p["p25"] <= p["p50"] <= p["p75"] <= p["p95"], (
            f"Percentile ordering violated: {p}"
        )

    def test_risk_fields(self) -> None:
        result = run_simulation(NORMAL_PAYLOAD)
        risk = result["risk"]
        assert "probability_of_loss" in risk
        assert "var_95" in risk

    def test_scenarios_run_matches_requested(self) -> None:
        for runs in [100, 1000, 5000]:
            payload = {**NORMAL_PAYLOAD, "runs": runs}
            result = run_simulation(payload)
            assert result["scenarios_run"] == runs


# ─── Distribution Tests ────────────────────────────────────────────────────────

class TestDistributions:
    def test_normal_distribution_mean_accuracy(self) -> None:
        """Normal distribution mean should be within 2% of specified mean."""
        result = run_simulation(NORMAL_PAYLOAD)
        mean = result["summary"]["mean"]
        expected_mean = 100000
        assert abs(mean - expected_mean) / expected_mean < 0.02, (
            f"Normal distribution mean {mean:.0f} deviates more than 2% from {expected_mean}"
        )

    def test_uniform_distribution_bounds(self) -> None:
        """Uniform distribution p5 and p95 should be close to actual bounds."""
        payload = {
            "runs": 10000,
            "seed": 42,
            "variables": [
                {"name": "x", "distribution": "uniform", "params": {"low": 0, "high": 100}}
            ],
            "objective_function": "x",
        }
        result = run_simulation(payload)
        # With 10k samples, p5 ≈ 5 and p95 ≈ 95 for uniform(0,100)
        assert result["percentiles"]["p5"] < 10
        assert result["percentiles"]["p95"] > 90

    def test_triangular_distribution_mode(self) -> None:
        """Triangular distribution median should be near the mode."""
        payload = {
            "runs": 50000,
            "seed": 42,
            "variables": [
                {"name": "x", "distribution": "triangular", "params": {"low": 0, "mode": 50, "high": 100}}
            ],
            "objective_function": "x",
        }
        result = run_simulation(payload)
        # Median of triangular(0,50,100) is ~47-53
        assert 40 <= result["percentiles"]["p50"] <= 60

    def test_lognormal_positive_outcomes(self) -> None:
        """Lognormal distribution should only produce positive values."""
        payload = {
            "runs": 5000,
            "seed": 42,
            "variables": [
                {"name": "x", "distribution": "lognormal", "params": {"mean": 0, "std": 0.5}}
            ],
            "objective_function": "x",
        }
        result = run_simulation(payload)
        # Lognormal is always positive, so probability of loss should be 0
        assert result["risk"]["probability_of_loss"] == 0.0

    def test_fixed_distribution(self) -> None:
        """Fixed distribution should have std=0 and mean=value."""
        payload = {
            "runs": 1000,
            "seed": 42,
            "variables": [
                {"name": "x", "distribution": "fixed", "params": {"value": 42.0}}
            ],
            "objective_function": "x",
        }
        result = run_simulation(payload)
        assert abs(result["summary"]["mean"] - 42.0) < 0.001
        assert result["summary"]["std"] == 0.0


# ─── Objective Function Tests ──────────────────────────────────────────────────

class TestObjectiveFunction:
    def test_net_value_objective(self) -> None:
        """revenue - cost should produce lower mean than revenue alone."""
        payload_net = TRIANGULAR_PAYLOAD
        payload_rev_only = {
            **TRIANGULAR_PAYLOAD,
            "objective_function": "revenue",
        }
        result_net = run_simulation(payload_net)
        result_rev = run_simulation(payload_rev_only)
        # Net value (revenue - cost) must be less than revenue alone
        assert result_net["summary"]["mean"] < result_rev["summary"]["mean"]

    def test_probability_of_loss_range(self) -> None:
        """Probability of loss must be between 0 and 1."""
        result = run_simulation(TRIANGULAR_PAYLOAD)
        pol = result["risk"]["probability_of_loss"]
        assert 0.0 <= pol <= 1.0

    def test_all_positive_distribution_zero_loss(self) -> None:
        """Distribution entirely > 0 should have probability_of_loss == 0."""
        payload = {
            "runs": 5000,
            "seed": 42,
            "variables": [
                {"name": "x", "distribution": "uniform", "params": {"low": 1, "high": 100}}
            ],
            "objective_function": "x",
        }
        result = run_simulation(payload)
        assert result["risk"]["probability_of_loss"] == 0.0
