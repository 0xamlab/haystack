"""
Shared type definitions for the Codna Decision Engine.

ExprNode — AST node for expression evaluator (op codes 0-21).
VarSpec, CorrSpec, ScoringSpec, SimRequest — typed request structs (Phase 3).
Engine-config structs: TimeSeriesCfg, DecisionTreeCfg, ISCfg, ScenarioCfg, BootstrapCfg, MCMCCfg.
Result structs: SummaryStats, PercentileSet, RiskMetrics, DecisionEnvelopeMojo (Phase 5).

op codes:
  0=literal  1=var_ref  2=add    3=sub    4=mul    5=div
  6=neg      7=pow      8=ln     9=log10  10=log2  11=exp
 12=sqrt    13=abs     14=floor 15=ceil  16=round 17=min2
 18=max2    19=clip    20=ifgt0 21=mod
"""

# ── Expression AST node (existing) ────────────────────────────────────────────

struct ExprNode(Copyable, Movable):
    var op:      Int
    var fval:    Float64
    var var_idx: Int
    var left:    Int
    var right:   Int
    var extra:   Int  # third child for clip/if

    fn __init__(out self, op: Int, value: Float64, var_idx: Int, left: Int, right: Int):
        self.op = op; self.fval = value; self.var_idx = var_idx
        self.left = left; self.right = right; self.extra = -1

    fn __init__(out self, op: Int, value: Float64, var_idx: Int, left: Int, right: Int, extra: Int):
        self.op = op; self.fval = value; self.var_idx = var_idx
        self.left = left; self.right = right; self.extra = extra


# ── Variable specification struct ──────────────────────────────────────────────
# dist_type int codes: 0=normal 1=uniform 2=triangular 3=lognormal 4=fixed
#   5=beta 7=exponential 8=weibull 9=gamma 10=pert 11=bernoulli 12=poisson
#   13=discrete 14=student_t 15=cauchy 16=laplace 17=pareto 18=gumbel
#   19=rayleigh 20=arcsine 21=logistic 22=halfnormal 23=vonmises
#   24=neg_binomial 25=hypergeometric 26=categorical

struct VarSpec(Copyable, Movable):
    var name:      String
    var dist_type: Int     # int code matching distributions.mojo dt values
    var p0:        Float64
    var p1:        Float64
    var p2:        Float64
    var p3:        Float64
    # For discrete/categorical — index into SimRequest.disc_vals/disc_probs
    # -1 means not a discrete type
    var disc_idx:  Int

    fn __init__(out self, name: String, dist_type: Int,
                p0: Float64, p1: Float64, p2: Float64, p3: Float64,
                disc_idx: Int = -1):
        self.name = name; self.dist_type = dist_type
        self.p0 = p0; self.p1 = p1; self.p2 = p2; self.p3 = p3
        self.disc_idx = disc_idx


# ── Correlation specification ──────────────────────────────────────────────────

struct CorrSpec(Copyable, Movable):
    var var1_idx:    Int
    var var2_idx:    Int
    var coefficient: Float64

    fn __init__(out self, var1_idx: Int, var2_idx: Int, coefficient: Float64):
        self.var1_idx = var1_idx; self.var2_idx = var2_idx
        self.coefficient = coefficient


# ── Scoring weights ────────────────────────────────────────────────────────────

struct ScoringSpec(Copyable, Movable):
    var w_ev: Float64   # weight for expected value component (default 0.6)
    var w_dr: Float64   # weight for downside risk component (default 0.4)

    fn __init__(out self, w_ev: Float64 = 0.6, w_dr: Float64 = 0.4):
        self.w_ev = w_ev; self.w_dr = w_dr


# ── Engine-specific config structs ────────────────────────────────────────────

struct TimeSeriesCfg(Copyable, Movable):
    var model:         String   # "gbm" | "ou" | "arithmetic" | "compound"
    var initial_value: Float64
    var drift:         Float64
    var volatility:    Float64
    var dt:            Float64  # fraction of year per step
    var ou_theta:      Float64  # OU mean-reversion speed
    var ou_mu:         Float64  # OU long-run mean
    var autocorr:      Float64  # AR(1) coefficient
    var granularity:   String
    var horizons:      List[Int]
    var pct_levels:    List[Int]

    fn __init__(out self):
        self.model = "gbm"; self.initial_value = 100.0
        self.drift = 0.0; self.volatility = 0.20
        self.dt = 1.0 / 12.0; self.ou_theta = 0.5; self.ou_mu = 100.0
        self.autocorr = 0.0; self.granularity = "month"
        self.horizons = List[Int](); self.pct_levels = List[Int]()


struct DecisionTreeCfg(Copyable, Movable):
    # Raw JSON string of decision_tree_config — re-parsed inside decision_tree.mojo
    # because paths have nested per-path variable arrays that cannot be flattened
    # without a variable-length struct-of-structs.
    var raw_config: String

    fn __init__(out self, raw: String = ""):
        self.raw_config = raw


struct ISCfg(Copyable, Movable):
    var target_threshold: Float64
    var tail_direction:   String   # "lower" | "upper"
    var tilt_var_name:    String
    var tilt_override:    Float64

    fn __init__(out self):
        self.target_threshold = -1e30; self.tail_direction = "lower"
        self.tilt_var_name = ""; self.tilt_override = 0.0


struct ScenarioCfg(Copyable, Movable):
    # Raw JSON string of scenario_config — re-parsed inside scenario engine
    # because each scenario has per-scenario variable overrides.
    var raw_config: String

    fn __init__(out self, raw: String = ""):
        self.raw_config = raw


struct BootstrapCfg(Copyable, Movable):
    var statistic:       String    # "mean" | "median" | "std" | "sum" | ...
    var historical_data: List[Float64]
    var n_data:          Int

    fn __init__(out self):
        self.statistic = "mean"; self.historical_data = List[Float64](); self.n_data = 0


struct MCMCCfg(Copyable, Movable):
    var observed_data: List[Float64]
    var n_data:        Int
    var burn_in:       Int
    var n_chains:      Int
    var likelihood:    String   # "normal" | "lognormal"

    fn __init__(out self):
        self.observed_data = List[Float64](); self.n_data = 0
        self.burn_in = 1000; self.n_chains = 4; self.likelihood = "normal"


# ── Canonical simulation request struct ───────────────────────────────────────

struct SimRequest(Copyable, Movable):
    """
    Fully typed simulation request. Created once by parse_request() from raw JSON.
    No PythonObject fields — all data is native Mojo types.
    Engines receive a SimRequest and read only what they need.
    """
    var engine_type:      String
    var runs:             Int
    var seed:             Int       # -1 = no seed
    var workers:          Int       # 0 = auto
    var stream_mode:      Bool
    var checkpoint_every: Int
    var scoring:          ScoringSpec

    # Variables
    var n_vars:      Int
    var vars:        List[VarSpec]
    # Discrete distribution value/probability lookup tables
    # disc_vals[i] / disc_probs[i] correspond to VarSpec.disc_idx == i
    var disc_vals:   List[List[Float64]]
    var disc_probs:  List[List[Float64]]
    # Parallel arrays for hot-loop access (avoids struct field access overhead)
    var dt:          List[Int]
    var p0:          List[Float64]
    var p1:          List[Float64]
    var p2:          List[Float64]
    var p3:          List[Float64]
    var vnames:      List[String]

    # Correlations
    var n_corr: Int
    var corrs:  List[CorrSpec]

    # Objective functions ("|"-separated multi-output supported)
    var obj_fn:       String
    var n_objectives: Int
    var obj_fns:      List[String]

    # Engine-specific configs (only one is populated per request)
    var has_time_series_cfg:    Bool
    var has_decision_tree_cfg:  Bool
    var has_is_cfg:             Bool
    var has_scenario_cfg:       Bool
    var has_bootstrap_cfg:      Bool
    var has_mcmc_cfg:           Bool

    var time_series_cfg:   TimeSeriesCfg
    var decision_tree_cfg: DecisionTreeCfg
    var is_cfg:            ISCfg
    var scenario_cfg:      ScenarioCfg
    var bootstrap_cfg:     BootstrapCfg
    var mcmc_cfg:          MCMCCfg

    fn __init__(out self):
        self.engine_type = "monte_carlo"; self.runs = 10000
        self.seed = -1; self.workers = 0
        self.stream_mode = False; self.checkpoint_every = 1000
        self.scoring = ScoringSpec()
        self.n_vars = 0
        self.vars = List[VarSpec]()
        self.disc_vals = List[List[Float64]]()
        self.disc_probs = List[List[Float64]]()
        self.dt = List[Int](); self.p0 = List[Float64]()
        self.p1 = List[Float64](); self.p2 = List[Float64]()
        self.p3 = List[Float64](); self.vnames = List[String]()
        self.n_corr = 0; self.corrs = List[CorrSpec]()
        self.obj_fn = ""; self.n_objectives = 0; self.obj_fns = List[String]()
        self.has_time_series_cfg = False; self.has_decision_tree_cfg = False
        self.has_is_cfg = False; self.has_scenario_cfg = False
        self.has_bootstrap_cfg = False; self.has_mcmc_cfg = False
        self.time_series_cfg = TimeSeriesCfg()
        self.decision_tree_cfg = DecisionTreeCfg()
        self.is_cfg = ISCfg()
        self.scenario_cfg = ScenarioCfg()
        self.bootstrap_cfg = BootstrapCfg()
        self.mcmc_cfg = MCMCCfg()


# ── Result envelope structs (Phase 5) ─────────────────────────────────────────

struct SummaryStats(Copyable, Movable):
    var mean:     Float64
    var median:   Float64
    var std:      Float64
    var variance: Float64

    fn __init__(out self, mean: Float64 = 0.0, median: Float64 = 0.0,
                std: Float64 = 0.0, variance: Float64 = 0.0):
        self.mean = mean; self.median = median
        self.std = std; self.variance = variance


struct PercentileSet(Copyable, Movable):
    var p5:  Float64
    var p10: Float64
    var p25: Float64
    var p50: Float64
    var p75: Float64
    var p90: Float64
    var p95: Float64
    var p99: Float64

    fn __init__(out self):
        self.p5 = 0.0; self.p10 = 0.0; self.p25 = 0.0; self.p50 = 0.0
        self.p75 = 0.0; self.p90 = 0.0; self.p95 = 0.0; self.p99 = 0.0


struct RiskMetrics(Copyable, Movable):
    var probability_of_loss: Float64
    var var_95:              Float64
    var cvar_95:             Float64

    fn __init__(out self, pol: Float64 = 0.0, var95: Float64 = 0.0, cvar95: Float64 = 0.0):
        self.probability_of_loss = pol; self.var_95 = var95; self.cvar_95 = cvar95


struct DecisionEnvelopeMojo(Copyable, Movable):
    """
    Fully typed result envelope computed by output.mojo.
    Includes histogram bins, CDF points, and result_hash (all Mojo-native, Phase 5+6).
    """
    var engine_version:  String
    var engine_type:     String
    var simulation_model: String
    var scenarios_run:   Int
    var summary:         SummaryStats
    var percentiles:     PercentileSet
    var risk:            RiskMetrics
    var score:           Float64

    # Histogram (50 bins default)
    var n_hist_bins:  Int
    var hist_bins:    List[Float64]   # bin_lo values
    var hist_counts:  List[Int]

    # CDF (100 points default)
    var n_cdf_points: Int
    var cdf_x:        List[Float64]
    var cdf_y:        List[Float64]

    # SHA-256 hex string (64 chars) — computed by compute_result_hash()
    var result_hash:  String

    fn __init__(out self):
        self.engine_version = ""; self.engine_type = ""; self.simulation_model = ""
        self.scenarios_run = 0
        self.summary = SummaryStats()
        self.percentiles = PercentileSet()
        self.risk = RiskMetrics()
        self.score = 0.0
        self.n_hist_bins = 0; self.hist_bins = List[Float64](); self.hist_counts = List[Int]()
        self.n_cdf_points = 0; self.cdf_x = List[Float64](); self.cdf_y = List[Float64]()
        self.result_hash = ""
