"""
output.mojo — Typed result envelope construction (Phase 5).

Public API:
  compute_envelope()    — builds DecisionEnvelopeMojo from outcomes list
  serialize_envelope()  — renders DecisionEnvelopeMojo to JSON string
  compute_histogram()   — 50-bin histogram (bin_lo, counts)
  compute_cdf_points()  — 100-point CDF (x_values, cdf_y)
  compute_result_hash() — SHA-256 of canonical envelope JSON (pure Mojo)
  build_output()        — backward-compatible shim: calls compute_envelope + serialize_envelope

Protocol version 1 is injected into every serialized response as "_proto":1.
"""
from std.math import sqrt, abs as fabs
from stats import compute_mean, compute_variance, pctile, count_below_zero, fast_sort
from types import DecisionEnvelopeMojo, SummaryStats, PercentileSet, RiskMetrics
from sha256 import sha256_hex


# ── Helper result structs for multi-return ────────────────────────────────────

struct HistResult(Movable):
    var bin_lo: List[Float64]
    var counts: List[Int]

    def __init__(out self):
        self.bin_lo = List[Float64]()
        self.counts = List[Int]()


struct CdfResult(Movable):
    var x_vals: List[Float64]
    var cdf_y: List[Float64]

    def __init__(out self):
        self.x_vals = List[Float64]()
        self.cdf_y = List[Float64]()


# ── Histogram ─────────────────────────────────────────────────────────────────

def compute_histogram(
    outcomes: List[Float64], n: Int, n_bins: Int = 50
) -> HistResult:
    """
    Compute n_bins equal-width histogram over sorted outcomes.
    Returns HistResult(bin_lo, counts).
    Assumes outcomes is already sorted ascending (fast_sort called by caller).
    """
    var result = HistResult()

    if n == 0:
        return result^

    var lo = outcomes[0]; var hi = outcomes[n - 1]
    if lo == hi: hi = lo + 1.0
    var bin_width = (hi - lo) / Float64(n_bins)
    if bin_width <= 0.0: bin_width = 1.0

    # Pre-fill bins
    for b in range(n_bins):
        result.bin_lo.append(lo + Float64(b) * bin_width)
        result.counts.append(0)

    # Count outcomes into bins (linear scan — outcomes is sorted)
    for i in range(n):
        var v = outcomes[i]
        var b = Int((v - lo) / bin_width)
        if b < 0: b = 0
        if b >= n_bins: b = n_bins - 1
        result.counts[b] += 1

    return result^


# ── CDF ───────────────────────────────────────────────────────────────────────

def compute_cdf_points(
    outcomes: List[Float64], n: Int, n_points: Int = 100
) -> CdfResult:
    """
    Compute n_points CDF samples from sorted outcomes.
    Returns CdfResult(x_vals, cdf_y) where cdf_y[i] = P(X <= x_vals[i]).
    Assumes outcomes is already sorted ascending.
    """
    var result = CdfResult()

    if n == 0:
        return result^

    var step = max(1, n // n_points)
    var i    = 0
    while i < n:
        result.x_vals.append(outcomes[i])
        result.cdf_y.append(Float64(i + 1) / Float64(n))
        i += step

    # Always include the last point
    if len(result.x_vals) == 0 or result.x_vals[len(result.x_vals) - 1] != outcomes[n - 1]:
        result.x_vals.append(outcomes[n - 1])
        result.cdf_y.append(1.0)

    return result^


# ── SHA-256 result hash ────────────────────────────────────────────────────────

def compute_result_hash(canonical_json: String) -> String:
    """
    Compute SHA-256 of canonical_json using pure Mojo SHA-256.
    Called once per request — not in the hot simulation loop.
    Returns 64-char hex digest string.
    """
    return sha256_hex(canonical_json)


# ── Core envelope computation ─────────────────────────────────────────────────

def compute_envelope(
    mut outcomes: List[Float64], n: Int,
    engine_ver: String, engine_type: String, sim_model: String,
    w_ev: Float64, w_dr: Float64,
) -> DecisionEnvelopeMojo:
    """
    Compute a fully typed DecisionEnvelopeMojo from raw outcomes.
    Sorts outcomes in-place, computes all stats, histogram, CDF, and result_hash.
    """
    fast_sort(outcomes, n)

    var env = DecisionEnvelopeMojo()
    env.engine_version   = engine_ver
    env.engine_type      = engine_type
    env.simulation_model = sim_model
    env.scenarios_run    = n

    # Summary stats
    var mean_v = compute_mean(outcomes, n)
    var var_v  = compute_variance(outcomes, n, mean_v)
    var std_v  = sqrt(var_v) if var_v > 0.0 else 0.0
    env.summary = SummaryStats(mean_v, pctile(outcomes, n, 50), std_v, var_v)

    # Percentiles
    var pct = PercentileSet()
    pct.p5  = pctile(outcomes, n, 5);  pct.p10 = pctile(outcomes, n, 10)
    pct.p25 = pctile(outcomes, n, 25); pct.p50 = pctile(outcomes, n, 50)
    pct.p75 = pctile(outcomes, n, 75); pct.p90 = pctile(outcomes, n, 90)
    pct.p95 = pctile(outcomes, n, 95); pct.p99 = pctile(outcomes, n, 99)
    env.percentiles = pct^

    # Risk metrics
    var n_loss    = count_below_zero(outcomes, n)
    var prob_loss = Float64(n_loss) / Float64(n)
    env.risk = RiskMetrics(prob_loss, pctile(outcomes, n, 5), pctile(outcomes, n, 2))

    # Score
    var abs_m  = fabs(mean_v)
    var ev_n: Float64 = 0.5
    if abs_m > 0.0:
        ev_n = max(0.0, min(1.0, (mean_v + abs_m) / (2.0 * abs_m)))
    env.score = w_ev * ev_n + w_dr * (1.0 - prob_loss)

    # Histogram
    var hist_result = compute_histogram(outcomes, n, 50)
    env.hist_bins   = hist_result.bin_lo.copy()
    env.hist_counts = hist_result.counts.copy()
    env.n_hist_bins = len(env.hist_bins)

    # CDF
    var cdf_result  = compute_cdf_points(outcomes, n, 100)
    env.cdf_x       = cdf_result.x_vals.copy()
    env.cdf_y       = cdf_result.cdf_y.copy()
    env.n_cdf_points = len(env.cdf_x)

    return env^


# ── Serialization ─────────────────────────────────────────────────────────────

def serialize_envelope(
    mut env: DecisionEnvelopeMojo, extra_json: String
) -> String:
    """
    Render DecisionEnvelopeMojo to a JSON string.
    Injects "_proto":1 for framed protocol versioning.
    Injects histogram_data and cdf_data from Mojo-computed fields.
    Computes and injects result_hash.
    extra_json is appended verbatim (comma-prefixed if non-empty).
    """
    # Core envelope
    var s = (
        '{"_proto":1'
        + ',"engine_version":"' + env.engine_version + '"'
        + ',"engine_type":"' + env.engine_type + '"'
        + ',"simulation_model":"' + env.simulation_model + '"'
        + ',"scenarios_run":' + String(env.scenarios_run)
        + ',"summary":{"mean":' + String(env.summary.mean)
        + ',"median":' + String(env.summary.median)
        + ',"std":' + String(env.summary.std)
        + ',"variance":' + String(env.summary.variance) + '}'
        + ',"percentiles":{"p5":' + String(env.percentiles.p5)
        + ',"p10":' + String(env.percentiles.p10)
        + ',"p25":' + String(env.percentiles.p25)
        + ',"p50":' + String(env.percentiles.p50)
        + ',"p75":' + String(env.percentiles.p75)
        + ',"p90":' + String(env.percentiles.p90)
        + ',"p95":' + String(env.percentiles.p95)
        + ',"p99":' + String(env.percentiles.p99) + '}'
        + ',"risk":{"probability_of_loss":' + String(env.risk.probability_of_loss)
        + ',"var_95":' + String(env.risk.var_95)
        + ',"cvar_95":' + String(env.risk.cvar_95) + '}'
        + ',"score":' + String(env.score)
    )

    # Histogram data (Mojo-computed — consumed by chart_service.py Phase 6)
    if env.n_hist_bins > 0:
        s += ',"histogram_data":{"n_bins":' + String(env.n_hist_bins) + ',"bins":['
        for i in range(env.n_hist_bins):
            if i > 0: s += ","
            s += '{"bin_lo":' + String(env.hist_bins[i])
            s += ',"count":' + String(env.hist_counts[i]) + '}'
        s += "]}"

    # CDF data (Mojo-computed — consumed by chart_service.py Phase 6)
    if env.n_cdf_points > 0:
        s += ',"cdf_data":{"n_points":' + String(env.n_cdf_points) + ',"points":['
        for i in range(env.n_cdf_points):
            if i > 0: s += ","
            s += '{"x":' + String(env.cdf_x[i]) + ',"cdf":' + String(env.cdf_y[i]) + '}'
        s += "]}"

    # Extra engine-specific JSON fields
    if len(extra_json) > 0: s += ',' + extra_json

    # Result hash — computed last over stable envelope content
    var hash_input = (
        env.engine_version + '|' + env.engine_type + '|'
        + String(env.scenarios_run) + '|'
        + String(env.summary.mean) + '|'
        + String(env.summary.std) + '|'
        + String(env.risk.probability_of_loss) + '|'
        + String(env.score)
    )
    var rh = compute_result_hash(hash_input)
    env.result_hash = rh
    s += ',"result_hash":"' + rh + '"'

    s += '}'
    return s


# ── Backward-compatible shim ───────────────────────────────────────────────────

def build_output(
    mut outcomes: List[Float64], n: Int,
    engine_ver: String, engine_type: String, sim_model: String,
    w_ev: Float64, w_dr: Float64,
    extra_json: String
) -> String:
    """
    Backward-compatible entry point.
    Calls compute_envelope() + serialize_envelope().
    All callers of the old build_output() continue working unchanged.
    """
    var env = compute_envelope(outcomes, n, engine_ver, engine_type, sim_model, w_ev, w_dr)
    return serialize_envelope(env, extra_json)
