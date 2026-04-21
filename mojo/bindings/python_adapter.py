"""
Python simulation adapter.

Used as a fallback when the Mojo binary is not compiled.
Implements the same stdin/stdout JSON protocol as the Mojo engine.
This is NOT the production engine — it exists purely for local development
before the Mojo build is available.
"""
import json
import random
import statistics
import sys
from typing import Any

ENGINE_VERSION = "0.1.0-python-fallback"


def run_simulation(config: dict[str, Any]) -> dict[str, Any]:
    """Run Monte Carlo simulation using Python stdlib. Same output contract as Mojo engine."""
    runs = int(config.get("runs", 10000))
    seed_value = config.get("seed")
    variables = config.get("variables", [])
    objective_fn = config.get("objective_function", "")

    # Deterministic simulation fallback requires a seeded local PRNG, not crypto randomness.
    rng = random.Random(seed_value)  # noqa: S311

    outcomes: list[float] = []

    for _ in range(runs):
        sample_values: dict[str, float] = {}

        for var_config in variables:
            name = var_config["name"]
            dist = var_config["distribution"]
            params = var_config["params"]

            if dist == "normal":
                sample = rng.gauss(float(params["mean"]), float(params["std"]))
            elif dist == "uniform":
                sample = rng.uniform(float(params["low"]), float(params["high"]))
            elif dist == "triangular":
                sample = rng.triangular(
                    float(params["low"]),
                    float(params["high"]),
                    float(params["mode"]),
                )
            elif dist == "lognormal":
                sample = rng.lognormvariate(float(params["mean"]), float(params["std"]))
            elif dist == "fixed":
                sample = float(params["value"])
            else:
                sample = 0.0

            sample_values[name] = sample

        # Evaluate objective function
        if objective_fn:
            try:
                outcome = float(eval(objective_fn, {"__builtins__": {}}, sample_values))  # noqa: S307
            except Exception:
                outcome = sum(sample_values.values())
        elif sample_values:
            outcome = next(iter(sample_values.values()))
        else:
            outcome = 0.0

        outcomes.append(outcome)

    # ── Statistics ──────────────────────────────────────────────────────────
    sorted_outcomes = sorted(outcomes)
    n = len(sorted_outcomes)

    def percentile(p: float) -> float:
        idx = int((n - 1) * p / 100)
        return sorted_outcomes[idx]

    mean_val = statistics.mean(outcomes) if outcomes else 0.0
    median_val = statistics.median(outcomes) if outcomes else 0.0
    stdev_val = statistics.stdev(outcomes) if n > 1 else 0.0
    variance_val = statistics.variance(outcomes) if n > 1 else 0.0
    prob_loss = sum(1 for x in outcomes if x < 0) / max(n, 1)

    p5 = percentile(5)
    p25 = percentile(25)
    p50 = percentile(50)
    p75 = percentile(75)
    p95 = percentile(95)
    var_95 = p5

    # Decision score
    if abs(mean_val) > 0:
        ev_norm = max(0.0, min(1.0, (mean_val + abs(mean_val)) / (2 * abs(mean_val))))
    else:
        ev_norm = 0.5
    score = 0.6 * ev_norm + 0.4 * (1.0 - prob_loss)

    return {
        "engine_version": ENGINE_VERSION,
        "scenarios_run": runs,
        "summary": {
            "mean": mean_val,
            "median": median_val,
            "std": stdev_val,
            "variance": variance_val,
        },
        "percentiles": {
            "p5": p5,
            "p25": p25,
            "p50": p50,
            "p75": p75,
            "p95": p95,
        },
        "risk": {
            "probability_of_loss": prob_loss,
            "var_95": var_95,
        },
        "score": score,
    }


def main() -> None:
    """CLI entry point — mirrors the Mojo binary interface."""
    try:
        raw_input = sys.stdin.read()
        config = json.loads(raw_input)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"ERROR: Failed to parse input JSON: {exc}\n")
        sys.exit(1)

    result = run_simulation(config)
    sys.stdout.write(json.dumps(result))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
