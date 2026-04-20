"""Response schemas — the Decision Envelope returned by all simulation endpoints."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ─── DecisionPlan — headline structured output ────────────────────────────────

class RiskProfile(BaseModel):
    """Quantified downside and upside for a single outcome distribution."""
    model_config = ConfigDict(strict=False)
    p5: float = Field(..., description="5th-percentile outcome (downside risk floor)")
    p95: float = Field(..., description="95th-percentile outcome (upside ceiling)")
    probability_of_loss: float = Field(..., ge=0.0, le=1.0, description="P(outcome < 0)")
    var_95: float | None = Field(None, description="Value-at-Risk at 95% confidence")


class DecisionOption(BaseModel):
    """One named alternative in a multi-option decision comparison."""
    model_config = ConfigDict(strict=False)
    name: str
    rank: int = Field(..., ge=1)
    expected_value: float
    risk: RiskProfile
    score: float | None = Field(None, ge=0.0, le=1.0, description="Composite score (0–1)")


class DecisionPlan(BaseModel):
    """
    Structured, LLM-readable summary of the decision output.

    This is the headline object — it surfaces all decision-critical fields
    in a compact, consistent shape regardless of simulation model used.
    Populate ``options`` with all ranked alternatives when using /v1/recommend.
    """
    model_config = ConfigDict(strict=False)

    recommended_action: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    expected_value: float
    risk: RiskProfile
    options: list[DecisionOption] = Field(
        default_factory=list,
        description=(
            "All alternatives ranked by expected value. "
            "Single-element for simulate, multi for recommend."
        ),
    )
    rationale: str
    integrity: dict | None = Field(
        None,
        description="Cryptographic proof of inputs/outputs: {request_hash, result_hash}.",
    )
    calibration: str | None = Field(
        None,
        description=(
            "Human-readable calibration summary, "
            "e.g. '12 outcomes | bias=-8.3% (over-optimistic) | hit_rate=75%'. "
            "Null until MIN_SAMPLES (5) outcomes are recorded for this org."
        ),
    )


class PercentileSummary(BaseModel):
    model_config = ConfigDict(strict=False)
    p5: float
    p10: float | None = None
    p25: float
    p50: float
    p75: float
    p90: float | None = None
    p95: float
    p99: float | None = None


class MetricsSummary(BaseModel):
    model_config = ConfigDict(strict=True)
    expected_value: float
    median: float
    std_deviation: float
    variance: float
    probability_of_loss: float = Field(..., ge=0.0, le=1.0)
    var_95: float | None = None
    cvar_95: float | None = None


class RunMetadata(BaseModel):
    model_config = ConfigDict(strict=True)
    mode: str
    seed: int | None = None
    billing_units: int
    engine_version: str


class DecisionEnvelope(BaseModel):
    """Full decision output returned by /v1/simulate, /v1/recommend, and /v1/score."""
    model_config = ConfigDict(strict=False)

    run_id: uuid.UUID
    status: str = Field(default="completed")
    engine_version: str

    recommended_action: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: str

    metrics: MetricsSummary
    percentiles: PercentileSummary

    scenarios_run: int
    execution_ms: int
    metadata: RunMetadata

    # ─── Simulation model metadata ────────────────────────────────────────────
    simulation_model: str = Field(
        default="monte_carlo",
        description=(
            "Which simulation algorithm was used. "
            "Possible values: monte_carlo | qmc_sobol | lhs | bootstrap | scenario | sensitivity | "
            "mcmc | decision_tree | time_series | compare | importance_sampling"
        ),
    )
    engine_type: str | None = Field(
        None,
        description="Engine that ran the simulation (e.g. 'mojo-native-expr', 'lhs', 'mcmc')",
    )
    simulation_class: str = Field(
        default="predictive",
        description=(
            "High-level simulation contract class. "
            "Examples: predictive, scenario_analysis, sensitivity_analysis, decision_tree."
        ),
    )
    model_revision: str | None = Field(
        None,
        description="Stable engine or model revision used to generate this result.",
    )
    assumptions_hash: str | None = Field(
        None,
        description=(
            "Stable fingerprint of the validated simulation assumptions "
            "executed by the engine."
        ),
    )
    validated_inputs: dict | None = Field(
        None,
        description=(
            "Normalized summary of the validated request inputs used for execution. "
            "Includes mode, runs, variable counts, and model selection."
        ),
    )
    confidence_interval: dict | None = Field(
        None,
        description="Primary outcome confidence interval derived from the simulated distribution.",
    )
    request_id: str | None = Field(
        None,
        description="Correlation identifier propagated from the API request.",
    )

    # ─── Extended model results ───────────────────────────────────────────────
    scenario_analysis: dict | None = Field(
        None,
        description=(
            "Populated for simulation_model='scenario': "
            "expected_value, best_case, scenarios list"
        ),
    )
    sensitivity_analysis: dict | None = Field(
        None,
        description=(
            "Populated for simulation_model='sensitivity': "
            "tornado_chart, first_order_sobol, variable_importance"
        ),
    )
    bootstrap_result: dict | None = Field(
        None,
        description=(
            "Populated for simulation_model='bootstrap': "
            "statistic, observed_value, CI, bias, SE"
        ),
    )
    mcmc_result: dict | None = Field(
        None,
        description=(
            "Populated for simulation_model='mcmc': "
            "posterior summaries, R-hat, acceptance_rate"
        ),
    )

    # ─── Importance sampling result ───────────────────────────────────────────
    importance_sampling_result: dict | None = Field(
        None,
        description=(
            "Populated for simulation_model='importance_sampling'. Contains: "
            "tail_direction, target_threshold, tail_probability, tail_probability_se, "
            "cvar_tail, weighted_mean, weighted_std, theta (tilt parameter), tilt_variable, "
            "effective_sample_size, nominal_sample_size, "
            "variance_reduction_factor, naive_tail_count."
        ),
    )

    scenario_ranking: list[dict] | None = None
    sensitivity_ranking: list[dict] | None = None
    score: float | None = Field(None, ge=0.0, le=1.0)
    score_breakdown: dict | None = None
    created_at: datetime | None = None

    # ─── Decision tree ────────────────────────────────────────────────────────
    decision_tree_result: dict | None = Field(
        None,
        description=(
            "Populated for simulation_model='decision_tree': "
            "n_paths, expected_value, paths[]"
        ),
    )

    # ─── Time series ──────────────────────────────────────────────────────────
    time_series_result: dict | None = Field(
        None,
        description=(
            "Populated for simulation_model='time_series'. Contains: "
            "model, granularity, dt_years, initial_value, n_steps, "
            "fan_chart (per-horizon p5/p25/p50/p75/p95), terminal distribution, "
            "max_drawdown_pct, and optional sample_paths for visualization."
        ),
    )

    # ─── Universal Unit Context ───────────────────────────────────────────────
    formatted_result: dict | None = Field(
        None,
        description=(
            "Human-readable formatted output values with units. "
            "Populated when output_unit_specs or unit_spec is provided. "
            "Contains: mean_formatted, p5_formatted, p95_formatted, unit, unit_type, etc."
        ),
    )
    unit_context: dict | None = Field(
        None,
        description=(
            "Unit metadata for all variables and outputs. "
            "Contains per-variable unit type, code, precision, and display scale. "
            "Use this to reconstruct formatted values client-side."
        ),
    )
    unit_warnings: list[str] | None = Field(
        None,
        description=(
            "Non-fatal unit validation warnings "
            "(e.g. negative currency, out-of-range probability). "
            "Simulation still ran — these are advisory only."
        ),
    )

    # ─── Chart-ready output ───────────────────────────────────────────────────
    charts: dict | None = Field(
        None,
        description=(
            "Pre-computed Vega-Lite compatible chart specs for instant rendering. "
            "Populated when include_charts=true in the request or automatically "
            "for sensitivity/time_series engine types. "
            "Keys: 'histogram', 'cdf', 'tornado', 'fan_chart', 'scatter'. "
            "Each value is a complete Vega-Lite spec that can be passed to vega-embed."
        ),
    )
    histogram_data: dict | None = Field(
        None,
        description="Pre-computed histogram bins (50 bins) for the primary output distribution.",
    )

    # ─── DecisionPlan — headline structured output ────────────────────────────
    decision_plan: DecisionPlan | None = Field(
        None,
        description=(
            "Structured decision summary. Always populated by /v1/simulate and /v1/recommend. "
            "Contains: recommended_action, confidence, expected_value, risk (p5/p95/PoL), "
            "all ranked options, rationale, and integrity hashes."
        ),
    )

    # ─── Data Integrity — Full Chain of Custody ───────────────────────────────
    request_hash: str | None = Field(
        None,
        description=(
            "SHA-256 fingerprint of the INPUT payload (variables, distributions, "
            "objective function, seed). Cryptographic proof of what data was used "
            "to make this decision. Computed at submission time before simulation runs. "
            "Format: hex string, 64 chars."
        ),
    )
    result_hash: str | None = Field(
        None,
        description=(
            "SHA-256 fingerprint of this decision OUTPUT (64-char hex). "
            "Covers: run_id, request_hash (input binding), recommended_action, "
            "confidence, rationale, metrics, percentiles, scenarios_run, engine_version, "
            "simulation_model. Binds the decision to both its inputs AND outputs. "
            "Use to verify the decision has not been tampered with. "
            "Also returned as X-Decision-Hash response header."
        ),
    )


def build_decision_plan(
    envelope: "DecisionEnvelope",
    options: "list[DecisionOption] | None" = None,
) -> DecisionPlan:
    """
    Build a DecisionPlan from a DecisionEnvelope.

    For /v1/simulate:  call with no ``options`` — a single-option plan is built.
    For /v1/recommend: call with all ranked ActionResults already converted to DecisionOption.
    """
    risk = RiskProfile(
        p5=envelope.percentiles.p5,
        p95=envelope.percentiles.p95,
        probability_of_loss=envelope.metrics.probability_of_loss,
        var_95=envelope.metrics.var_95,
    )

    if options is None:
        options = [
            DecisionOption(
                name=envelope.recommended_action,
                rank=1,
                expected_value=envelope.metrics.expected_value,
                risk=risk,
                score=envelope.confidence,
            )
        ]

    integrity = None
    if envelope.request_hash or envelope.result_hash:
        integrity = {
            k: v for k, v in {
                "request_hash": envelope.request_hash,
                "result_hash":  envelope.result_hash,
            }.items() if v
        }

    return DecisionPlan(
        recommended_action=envelope.recommended_action,
        confidence=envelope.confidence,
        expected_value=envelope.metrics.expected_value,
        risk=risk,
        options=options,
        rationale=envelope.rationale,
        integrity=integrity,
    )
