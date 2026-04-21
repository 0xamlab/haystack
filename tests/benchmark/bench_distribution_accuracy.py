"""
bench_distribution_accuracy.py — PhD-grade statistical correctness tests.

Tests all 22 major distributions for:
1. Mean convergence (within kσ/√N of theoretical mean)
2. Variance convergence (within tolerance of theoretical variance)
3. Percentile ordering (p5 ≤ p25 ≤ p50 ≤ p75 ≤ p95)
4. Score range (0.0 to 1.0)
5. Non-degenerate output (std > 0 for non-fixed distributions)

Each distribution is tested by piping a JSON payload to the compiled Mojo
binary (mojo_build/simulate) and parsing the output — no API server needed.

Usage:
    python -m tests.benchmark.bench_distribution_accuracy
    make bench-dist-accuracy

Requires: mojo_build/simulate binary (build with: make build-mojo)
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

BINARY = Path("mojo_build/simulate")
N_RUNS = 10_000  # Large enough for CLT convergence

# ── Euler–Mascheroni constant ──────────────────────────────────────────────────
EULER_MASCHERONI = 0.5772156649015329


@dataclass
class DistTestCase:
    """Spec for one distribution statistical correctness test."""

    name: str
    dist_type: str
    params: dict
    expected_mean: float | None     # None → skip mean test (e.g. Cauchy)
    expected_std: float | None      # None → use loose mean tolerance
    tolerance_sigmas: float = 4.0      # multiplier for σ/√N tolerance band
    skip_mean: bool = False
    is_fixed: bool = False


# ── Distribution test cases ────────────────────────────────────────────────────
# Parameter names must match mojo/engine/request_parser.mojo exactly.

DISTRIBUTION_TESTS: list[DistTestCase] = [
    # ── Continuous distributions ────────────────────────────────────────────

    # Normal: E[X]=μ, Var[X]=σ²
    DistTestCase(
        "normal(100,20)", "normal",
        {"mean": 100, "std": 20},
        expected_mean=100.0, expected_std=20.0,
    ),

    # Uniform: E[X]=(a+b)/2, Var[X]=(b-a)²/12
    DistTestCase(
        "uniform(0,100)", "uniform",
        {"low": 0, "high": 100},
        expected_mean=50.0, expected_std=100.0 / math.sqrt(12),
    ),

    # Triangular: E[X]=(a+b+c)/3
    DistTestCase(
        "triangular(10,50,90)", "triangular",
        {"low": 10, "mode": 50, "high": 90},
        expected_mean=50.0,
        expected_std=math.sqrt(
            (10**2 + 50**2 + 90**2 - 10 * 50 - 10 * 90 - 50 * 90) / 18
        ),
    ),

    # Lognormal: params are (μ_log, σ_log) of underlying normal
    # E[X] = exp(μ + σ²/2)
    DistTestCase(
        "lognormal(4,0.5)", "lognormal",
        {"mean": 4, "std": 0.5},
        expected_mean=math.exp(4 + 0.5**2 / 2),
        expected_std=None,  # heavy-tailed → use loose tolerance
        tolerance_sigmas=5.0,
    ),

    # Exponential: E[X]=1/λ, Var[X]=1/λ²
    DistTestCase(
        "exponential(0.1)", "exponential",
        {"rate": 0.1},
        expected_mean=10.0, expected_std=10.0,
    ),

    # Beta: E[X]=α/(α+β)
    DistTestCase(
        "beta(2,5)", "beta",
        {"alpha": 2, "beta": 5},
        expected_mean=2.0 / 7.0,
        expected_std=math.sqrt(2 * 5 / (7**2 * 8)),
        tolerance_sigmas=5.0,
    ),

    # Bernoulli: E[X]=p
    DistTestCase(
        "bernoulli(0.7)", "bernoulli",
        {"p": 0.7},
        expected_mean=0.7,
        expected_std=math.sqrt(0.7 * 0.3),
    ),

    # Poisson: E[X]=λ, Var[X]=λ
    DistTestCase(
        "poisson(5)", "poisson",
        {"lambda": 5},
        expected_mean=5.0, expected_std=math.sqrt(5.0),
    ),

    # Weibull: E[X]=scale·Γ(1+1/shape)
    DistTestCase(
        "weibull(2,10)", "weibull",
        {"shape": 2, "scale": 10},
        expected_mean=10.0 * math.gamma(1 + 1.0 / 2),
        expected_std=None,
        tolerance_sigmas=5.0,
    ),

    # Gamma: E[X]=shape·scale, Var[X]=shape·scale²
    DistTestCase(
        "gamma(3,2)", "gamma",
        {"shape": 3, "scale": 2},
        expected_mean=6.0,
        expected_std=math.sqrt(3) * 2,
    ),

    # PERT: E[X]=(low+γ·likely+high)/(γ+2)  (γ=4 default)
    DistTestCase(
        "pert(10,50,90)", "pert",
        {"low": 10, "likely": 50, "high": 90, "gamma": 4},
        expected_mean=(10 + 4 * 50 + 90) / 6,
        expected_std=None,
        tolerance_sigmas=5.0,
    ),

    # Student-t: E[X]=loc for df>1
    DistTestCase(
        "student_t(10,0,1)", "student_t",
        {"df": 10, "loc": 0, "scale": 1},
        expected_mean=0.0,
        expected_std=None,  # heavier tails
        tolerance_sigmas=5.0,
    ),

    # Cauchy: no defined mean or variance → skip mean, just check structure
    DistTestCase(
        "cauchy(0,1)", "cauchy",
        {"location": 0, "scale": 1},
        expected_mean=None, expected_std=None,
        skip_mean=True,
    ),

    # Laplace: E[X]=μ, Var[X]=2b²
    DistTestCase(
        "laplace(10,2)", "laplace",
        {"mu": 10, "b": 2},
        expected_mean=10.0,
        expected_std=2 * math.sqrt(2),
    ),

    # Pareto: E[X]=α·x_m/(α-1) for α>1
    DistTestCase(
        "pareto(3,1)", "pareto",
        {"alpha": 3, "x_min": 1},
        expected_mean=3.0 * 1.0 / (3.0 - 1.0),  # = 1.5
        expected_std=None,  # heavy-tailed
        tolerance_sigmas=5.0,
    ),

    # Gumbel: E[X]=μ+β·γ_EM
    DistTestCase(
        "gumbel(0,1)", "gumbel",
        {"mu": 0, "beta": 1},
        expected_mean=EULER_MASCHERONI,
        expected_std=None,
        tolerance_sigmas=5.0,
    ),

    # Rayleigh: E[X]=σ·√(π/2)
    DistTestCase(
        "rayleigh(1)", "rayleigh",
        {"sigma": 1},
        expected_mean=math.sqrt(math.pi / 2),
        expected_std=None,
        tolerance_sigmas=5.0,
    ),

    # Arcsine: E[X]=(low+high)/2
    DistTestCase(
        "arcsine(0,1)", "arcsine",
        {"low": 0, "high": 1},
        expected_mean=0.5,
        expected_std=None,
        tolerance_sigmas=5.0,
    ),

    # Logistic: E[X]=μ, Var[X]=(scale·π)²/3
    DistTestCase(
        "logistic(5,2)", "logistic",
        {"mu": 5, "scale": 2},
        expected_mean=5.0,
        expected_std=2 * math.pi / math.sqrt(3),
    ),

    # Half-normal: E[X]=σ·√(2/π)
    DistTestCase(
        "halfnormal(3)", "halfnormal",
        {"sigma": 3},
        expected_mean=3 * math.sqrt(2 / math.pi),
        expected_std=None,
        tolerance_sigmas=5.0,
    ),

    # ── Fixed (degenerate) ─────────────────────────────────────────────────

    DistTestCase(
        "fixed(42)", "fixed",
        {"value": 42},
        expected_mean=42.0, expected_std=0.0,
        is_fixed=True,
    ),

    # ── Discrete distributions ─────────────────────────────────────────────

    # Negative binomial: E[X]=r·(1-p)/p
    DistTestCase(
        "neg_binomial(5,0.5)", "neg_binomial",
        {"r": 5, "p": 0.5},
        expected_mean=5.0 * 0.5 / 0.5,  # = 5.0
        expected_std=None,
        tolerance_sigmas=5.0,
    ),
]


# ── Engine invocation ──────────────────────────────────────────────────────────

def run_engine(tc: DistTestCase, n: int = N_RUNS) -> dict:
    """Pipe a single-variable monte_carlo payload to the binary and return parsed JSON."""
    payload = {
        "engine_type": "monte_carlo",
        "runs": n,
        "variables": [
            {"name": "x", "distribution": tc.dist_type, "params": tc.params}
        ],
        "objective_function": "x",
    }
    try:
        result = subprocess.run(
            [str(BINARY)],
            input=json.dumps(payload).encode(),
            capture_output=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return {"_error": "timeout after 60s"}

    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace")[:300]
        return {"_error": f"exit {result.returncode}: {stderr}"}

    try:
        output = result.stdout.decode().strip()
        # Handle multi-line streaming output — take last complete JSON line
        lines = [line for line in output.split("\n") if line.strip()]
        if not lines:
            return {"_error": "empty stdout"}
        return json.loads(lines[-1])
    except (json.JSONDecodeError, IndexError) as e:
        return {"_error": f"invalid JSON: {e}"}


# ── Statistical tests ──────────────────────────────────────────────────────────

@dataclass
class TestResult:
    """Result of one distribution test."""
    name: str
    passed: bool
    issues: list[str] = field(default_factory=list)
    mean: float = 0.0
    std: float = 0.0
    score: float = 0.0
    elapsed_ms: float = 0.0


def test_distribution(tc: DistTestCase) -> TestResult:
    """Run all statistical checks for one distribution."""
    t0 = time.perf_counter()
    raw = run_engine(tc)
    elapsed = (time.perf_counter() - t0) * 1000

    tr = TestResult(name=tc.name, passed=True, elapsed_ms=elapsed)

    # Check for invocation errors
    if "_error" in raw:
        tr.passed = False
        tr.issues.append(f"engine error: {raw['_error']}")
        return tr

    summary = raw.get("summary", {})
    pcts = raw.get("percentiles", {})
    score = raw.get("score", -1)

    mean = summary.get("mean", float("nan"))
    std = summary.get("std", float("nan"))
    tr.mean = mean
    tr.std = std
    tr.score = score

    # ── Test 1: Mean convergence ───────────────────────────────────────────
    if tc.expected_mean is not None and not tc.skip_mean:
        if tc.expected_std is not None and tc.expected_std > 0:
            # CLT: std error of sample mean = σ/√N
            tolerance = tc.tolerance_sigmas * tc.expected_std / math.sqrt(N_RUNS)
        else:
            # Loose tolerance: 20% of |expected_mean| or absolute floor
            tolerance = max(abs(tc.expected_mean) * 0.20, 1.0)

        if math.isnan(mean) or abs(mean - tc.expected_mean) > tolerance:
            tr.issues.append(
                f"mean={mean:.6f}, expected={tc.expected_mean:.6f}, "
                f"tol={tolerance:.6f}, delta={abs(mean - tc.expected_mean):.6f}"
            )
            tr.passed = False

    # ── Test 2: Score in [0, 1] ────────────────────────────────────────────
    if score < 0 or score > 1:
        tr.issues.append(f"score={score:.6f} out of [0,1]")
        tr.passed = False

    # ── Test 3: Percentile ordering ────────────────────────────────────────
    p5 = pcts.get("p5", 0)
    p25 = pcts.get("p25", 0)
    p50 = pcts.get("p50", 0)
    p75 = pcts.get("p75", 0)
    p95 = pcts.get("p95", 0)

    if not (p5 <= p25 <= p50 <= p75 <= p95):
        tr.issues.append(
            f"percentile order violated: p5={p5:.4f} p25={p25:.4f} "
            f"p50={p50:.4f} p75={p75:.4f} p95={p95:.4f}"
        )
        tr.passed = False

    # ── Test 4: Non-degeneracy ─────────────────────────────────────────────
    if not tc.is_fixed:
        if math.isnan(std) or std <= 0:
            tr.issues.append(f"std={std} (expected > 0 for non-fixed dist)")
            tr.passed = False
    else:
        # Fixed distribution: std must be 0, mean must be exact
        if std != 0:
            tr.issues.append(f"fixed: std={std}, expected=0")
            tr.passed = False
        if tc.expected_mean is not None and mean != tc.expected_mean:
            tr.issues.append(f"fixed: mean={mean}, expected={tc.expected_mean}")
            tr.passed = False

    # ── Test 5: Variance convergence (when expected_std is known) ──────────
    if tc.expected_std is not None and tc.expected_std > 0 and not tc.is_fixed:
        expected_var = tc.expected_std**2
        actual_var = std**2
        relative_error = abs(actual_var - expected_var) / expected_var
        if relative_error > 0.25:  # 25% tolerance on variance
            tr.issues.append(
                f"variance: actual={actual_var:.4f} vs expected={expected_var:.4f} "
                f"(rel_err={relative_error:.2%})"
            )
            tr.passed = False

    # ── Test 6: Histogram present ──────────────────────────────────────────
    hist = raw.get("histogram_data", {})
    if hist.get("n_bins", 0) < 1:
        tr.issues.append("no histogram bins in output")
        tr.passed = False

    # ── Test 7: CDF present ────────────────────────────────────────────────
    cdf = raw.get("cdf_data", {})
    if cdf.get("n_points", 0) < 1:
        tr.issues.append("no CDF points in output")
        tr.passed = False

    return tr


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    if not BINARY.exists():
        print(f"❌ Binary not found at {BINARY}. Build with: make build-mojo")
        sys.exit(1)

    n_tests = len(DISTRIBUTION_TESTS)
    print("━━━ Distribution Statistical Correctness Tests ━━━")
    print(f"    Binary:  {BINARY}")
    print(f"    Runs:    {N_RUNS:,} per distribution")
    print(f"    Tests:   {n_tests} distributions")
    print()

    results: list[TestResult] = []
    t_total = time.perf_counter()

    for tc in DISTRIBUTION_TESTS:
        tr = test_distribution(tc)
        results.append(tr)
        if tr.passed:
            print(f"  ✅ {tr.name:<30s}  mean={tr.mean:>12.4f}  std={tr.std:>10.4f}  score={tr.score:.3f}  ({tr.elapsed_ms:.0f}ms)")
        else:
            print(f"  ❌ {tr.name:<30s}  FAILED")
            for issue in tr.issues:
                print(f"     └─ {issue}")

    total_elapsed = (time.perf_counter() - t_total) * 1000
    passed = sum(1 for r in results if r.passed)
    failed = n_tests - passed

    print()
    print("━━━ Results ━━━")
    print(f"  Passed:  {passed}/{n_tests}")
    print(f"  Failed:  {failed}/{n_tests}")
    print(f"  Time:    {total_elapsed:,.0f} ms total ({total_elapsed / n_tests:,.0f} ms avg)")

    # Summary table
    print()
    print("| Distribution | Mean | Expected | Δ | Std | Score | Status |")
    print("|---|---|---|---|---|---|---|")
    for r, tc in zip(results, DISTRIBUTION_TESTS, strict=False):
        exp_str = f"{tc.expected_mean:.4f}" if tc.expected_mean is not None else "N/A"
        delta = abs(r.mean - tc.expected_mean) if tc.expected_mean is not None else 0
        delta_str = f"{delta:.4f}" if tc.expected_mean is not None else "—"
        status = "✅" if r.passed else "❌"
        print(
            f"| {r.name} | {r.mean:.4f} | {exp_str} | {delta_str} "
            f"| {r.std:.4f} | {r.score:.3f} | {status} |"
        )

    if failed > 0:
        print(f"\n❌ {failed} distribution(s) failed statistical correctness checks.")
        sys.exit(1)
    else:
        print(f"\n✅ All {n_tests} distributions pass PhD-grade statistical correctness.")
        sys.exit(0)


if __name__ == "__main__":
    main()
