"""degradation_state — per-car pace and tyre-degradation estimation from observed lap times.

This is the first MODELLED quantity in the pipeline. Everything upstream of it (position, laps,
compound, pit counts, track status) is an observation the timing feed stated, merged forward. Clean-air
pace and degradation slope are inferred, and the strategy board depends on them, so they live here.

Two-state filter per car over

    x = [beta0, beta1]        beta0 = pace offset (s/lap)
                              beta1 = residual degradation slope (s/lap per lap of tyre age)

with observation model  z = beta0 + beta1 * a  at tyre age a, i.e. H = [1, a].

Why a filter rather than a per-stint regression: a single-lap estimate lets one contaminated
observation move the whole board. The reference system traced a live anomaly -- a P8 car showing an
implausible 55.8% win probability -- to exactly that, an out-lap polluting a single-lap pace fit. The
filter carries uncertainty explicitly so one bad lap is weighted, not obeyed.

Deliberate modelling choices, each of which prevents a specific failure:

  * out-laps, in-laps and neutralised laps are EXCLUDED from updates. A car behind a safety car is not
    revealing its pace, and an out-lap on cold tyres is not either. Including them biases beta1 upward
    and makes every stint look like it is falling off a cliff.
  * dirty-air laps inflate measurement noise rather than being discarded. The information is real but
    degraded; throwing it away loses laps we cannot spare on short stints.
  * a compound change RESETS the slope variance to its prior while CARRYING the pace offset. The car's
    intrinsic pace persists across a stop; its degradation slope does not.
  * the tyre-only wear component is clamped to a physically plausible band. An unclamped fit goes
    negative -- fuel burn and track evolution improve lap time as a stint progresses -- producing a
    model in which tyres get faster forever, which a plan optimizer will happily exploit with an
    impossible 50-lap stint. The clamp is not cosmetic; it is what makes the optimizer honest.
"""

from std.math import sqrt

alias DEFAULT_LAP_NOISE: Float64 = 0.18
alias DIRTY_AIR_NOISE_FACTOR: Float64 = 4.0
alias WEAR_CLAMP_LO: Float64 = 0.0
alias WEAR_CLAMP_HI: Float64 = 0.22

# lap-exclusion flags, bitwise so one Int carries the whole reason set
alias LAP_GREEN: Int = 0
alias LAP_OUT: Int = 1
alias LAP_IN: Int = 2
alias LAP_NEUTRALISED: Int = 4
alias LAP_DIRTY_AIR: Int = 8


struct PaceState(Copyable, Movable):
    """Two-state pace filter: [beta0, beta1] with its 2x2 covariance (symmetric, so p01 == p10)."""

    var beta0: Float64
    var beta1: Float64
    var p00: Float64
    var p01: Float64
    var p11: Float64
    var n_updates: Int
    var n_excluded: Int

    def __init__(
        out self, beta0: Float64, beta1: Float64,
        p00: Float64, p01: Float64, p11: Float64,
        n_updates: Int, n_excluded: Int,
    ):
        self.beta0 = beta0
        self.beta1 = beta1
        self.p00 = p00
        self.p01 = p01
        self.p11 = p11
        self.n_updates = n_updates
        self.n_excluded = n_excluded


def pace_state_init(
    beta0_prior: Float64, beta1_prior: Float64, var0: Float64, var1: Float64
) -> PaceState:
    """Fresh filter from a prior pace offset and slope with independent variances."""
    return PaceState(beta0_prior, beta1_prior, var0, 0.0, var1, 0, 0)


def load_corrected_rate(lap_time: Float64, laps_remaining: Float64, fuel_effect: Float64) -> Float64:
    """Remove the fuel-burn benefit so the residual reflects tyre state, not a lightening car.

    A raw lap-time series conflates tyre wear with fuel burn and track evolution. Without this the
    fitted slope is frequently NEGATIVE, and the clamp below would then do all the work.
    """
    return lap_time - fuel_effect * laps_remaining


def wear_clamp(slope: Float64) -> Float64:
    """Clamp the tyre-only wear component to a physically plausible band."""
    if slope < WEAR_CLAMP_LO:
        return WEAR_CLAMP_LO
    if slope > WEAR_CLAMP_HI:
        return WEAR_CLAMP_HI
    return slope


def sample_is_usable(flags: Int) -> Bool:
    """Out-laps, in-laps and neutralised laps reveal no pace. Dirty air is usable but noisier."""
    if flags & LAP_OUT != 0:
        return False
    if flags & LAP_IN != 0:
        return False
    if flags & LAP_NEUTRALISED != 0:
        return False
    return True


def pace_kalman_update(
    state: PaceState, lap_time: Float64, tyre_age: Float64,
    flags: Int, lap_noise: Float64, drift_slope: Float64,
) -> PaceState:
    """One filter step. Returns the state unchanged (bar an exclusion count) for unusable laps.

    Random-walk process model: the state does not move deterministically, its uncertainty grows.
    """
    if not sample_is_usable(flags):
        return PaceState(
            state.beta0, state.beta1, state.p00, state.p01, state.p11,
            state.n_updates, state.n_excluded + 1,
        )

    # predict: x unchanged, P += Q  (slope allowed to drift more than the offset)
    var p00 = state.p00 + drift_slope * 0.25
    var p01 = state.p01
    var p11 = state.p11 + drift_slope

    # measurement noise, inflated in dirty air
    var r = lap_noise * lap_noise
    if flags & LAP_DIRTY_AIR != 0:
        r = r * DIRTY_AIR_NOISE_FACTOR

    # H = [1, a];  S = H P Hᵀ + R
    var a = tyre_age
    var hp0 = p00 + a * p01
    var hp1 = p01 + a * p11
    var s = hp0 + a * hp1 + r
    if s <= 0.0:
        return state.copy()

    # K = P Hᵀ / S
    var k0 = hp0 / s
    var k1 = hp1 / s

    var residual = lap_time - (state.beta0 + state.beta1 * a)
    var beta0 = state.beta0 + k0 * residual
    var beta1 = state.beta1 + k1 * residual

    # P = (I - K H) P
    var n00 = p00 - k0 * hp0
    var n01 = p01 - k0 * hp1
    var n11 = p11 - k1 * hp1

    return PaceState(beta0, beta1, n00, n01, n11, state.n_updates + 1, state.n_excluded)


def pace_reset_for_compound(state: PaceState, slope_prior: Float64, slope_var: Float64) -> PaceState:
    """Carry the pace offset across a pit stop, reset the slope and its variance.

    Intrinsic car pace persists through a stop; the degradation slope of a fresh compound does not.
    Carrying the slope makes the first laps of a new stint look like the end of the old one.
    """
    return PaceState(state.beta0, slope_prior, state.p00, 0.0, slope_var,
                     state.n_updates, state.n_excluded)


def pace_predict(state: PaceState, tyre_age: Float64) -> Float64:
    """Predicted lap time at a given tyre age, with the wear component clamped."""
    return state.beta0 + wear_clamp(state.beta1) * tyre_age


def pace_offset_stderr(state: PaceState) -> Float64:
    """Standard error of the pace offset — the filter's own uncertainty, not sampling error."""
    if state.p00 <= 0.0:
        return 0.0
    return sqrt(state.p00)


def pace_slope_stderr(state: PaceState) -> Float64:
    """Standard error of the degradation slope."""
    if state.p11 <= 0.0:
        return 0.0
    return sqrt(state.p11)


def pace_kalman_run(
    lap_times: List[Float64], tyre_ages: List[Float64], flags: List[Int],
    beta0_prior: Float64, beta1_prior: Float64, var0: Float64, var1: Float64,
    lap_noise: Float64, drift_slope: Float64,
) -> PaceState:
    """Run the filter over one stint's laps. Inputs must be equal length; short lists stop early."""
    var state = pace_state_init(beta0_prior, beta1_prior, var0, var1)
    var n = len(lap_times)
    if len(tyre_ages) < n:
        n = len(tyre_ages)
    if len(flags) < n:
        n = len(flags)
    for i in range(n):
        state = pace_kalman_update(
            state, lap_times[i], tyre_ages[i], flags[i], lap_noise, drift_slope
        )
    return state^


# ── deterministic zero-argument probes ────────────────────────────────────────


def degradation_state_version() -> String:
    """Contract identifier for this estimator. Deterministic, zero-argument."""
    return String("degradation-state/v1")


def wear_clamp_bounds() -> List[Float64]:
    """The physically plausible tyre-only wear band, s/lap. Deterministic, zero-argument."""
    var out = List[Float64]()
    out.append(WEAR_CLAMP_LO)
    out.append(WEAR_CLAMP_HI)
    return out^


def degradation_state_selftest() -> Float64:
    """Fit a known linear degradation and return the recovered slope. Deterministic, zero-argument.

    Truth is 0.05 s/lap of age on a 90 s base over 20 laps; a correct filter recovers it closely.
    """
    var times = List[Float64]()
    var ages = List[Float64]()
    var flags = List[Int]()
    for i in range(20):
        var a = Float64(i)
        ages.append(a)
        times.append(90.0 + 0.05 * a)
        flags.append(LAP_GREEN)
    var st = pace_kalman_run(times, ages, flags, 90.0, 0.0, 1.0, 0.01, 0.05, 0.0005)
    return st.beta1
