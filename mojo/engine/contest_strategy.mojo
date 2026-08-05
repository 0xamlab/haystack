"""contest_strategy — full-field Monte Carlo pit board under common random numbers.

ONE coarse call per decision. The whole N x C x laps simulation runs inside `option_board`, which
returns aggregates only. That is deliberate: per-call dispatch is framed JSON over a socket at ~1-4 ms
with a 1 MiB payload cap, so N calls would cost more in transport than the simulation costs in compute.
Race state for 22 cars is a few hundred bytes; the replication matrix never crosses the boundary.

Placed here as a callable library function rather than an engine_type under engines/, because engines/
is excluded from the callable library inventory by design. A library function is reachable through the
SDK and the socket with no main.mojo registration, which is what local-SDK-only consumption needs.

WHY COMMON RANDOM NUMBERS, CONCRETELY. The four options are compared by DIFFERENCE. If each drew its
own safety car, one option would win because its world happened to be kind, and the difference would be
dominated by sampling noise rather than strategy. So every exogenous draw is addressed by
(replication, lap, car, process) via counter_rng and is IDENTICAL across options -- the option index
appears nowhere in the RNG coordinates. Only endogenous consequences differ, because state differs.
This is what makes a 2 pp delta meaningful at N=2,000 instead of needing an order of magnitude more.

Modelled content is the observable strategy core: lap time with fuel correction and clamped
degradation, circuit pit loss with a right-tailed service time, in-lap and out-lap penalties, SC and
VSC regimes with pit-loss discounts, dirty-air loss, and retirement.

DECLARED SIMPLIFICATION: rivals hold their current tyres to the end (no further stops). A rival
covering our undercut is not modelled. That is the reference system's main declared residual error
source too, and it is a policy-identification problem rather than a compute one -- we cannot observe a
rival's tyre inventory, team orders or crew availability. Stated rather than papered over; the board is
therefore a decision-support contrast against a fixed opponent plan, not a game solution.
"""

from math import exp, log, sqrt
from std.algorithm import parallelize
from std.sys import info
from memory import UnsafePointer

from counter_rng import (
    philox_word,
    rng_uniform,
    rng_normal,
    PROCESS_SAFETY_CAR,
    PROCESS_VSC,
    PROCESS_LAP_NOISE,
    PROCESS_PIT_SERVICE,
    PROCESS_RETIREMENT,
    PROCESS_OVERTAKE,
    PROCESS_CAR_FORM,
    PROCESS_BOOTSTRAP,
    GLOBAL_SENTINEL,
)
from degradation_state import wear_clamp


fn wear_penalty(
    deg: Float64, age: Float64, cliff_age: Float64, cliff_slope: Float64
) -> Float64:
    """Linear wear plus the cliff — ONE definition, so the oracle and the board price tyres alike.

    The plan requires the optimizer to price a stop identically to the simulator; the same applies to
    what a stop BUYS. Two copies of a piecewise function is how that quietly stops being true.
    """
    var pen = deg * age
    if age > cliff_age:
        pen += cliff_slope * (age - cliff_age)
    return pen

alias N_OPTIONS: Int = 4
alias OPT_STAY: Int = 0
alias OPT_BOX_NOW: Int = 1
alias OPT_BOX_1: Int = 2
alias OPT_BOX_2: Int = 3

alias VERDICT_RECOMMENDED: Int = 1
alias VERDICT_INCONCLUSIVE: Int = 2

# params[] layout — flat so the signature stays short and the contract is explicit
alias P_PIT_LOSS: Int = 0
alias P_LAP_NOISE: Int = 1
alias P_DNF_PROB: Int = 2
alias P_SC_LAMBDA: Int = 3
alias P_SC_PACE_MULT: Int = 4
alias P_SC_PIT_FACTOR: Int = 5
alias P_VSC_LAMBDA: Int = 6
alias P_VSC_PACE_MULT: Int = 7
alias P_VSC_PIT_FACTOR: Int = 8
alias P_DIRTY_WINDOW: Int = 9
alias P_DIRTY_LOSS: Int = 10
alias P_FUEL_EFFECT: Int = 11
alias P_DELTA_OUT: Int = 12
alias P_DELTA_IN: Int = 13
alias P_SIGMA_PIT: Int = 14
alias P_EPSILON: Int = 15
alias P_MARGIN: Int = 16
# The interaction layer. Everything above is a per-car marginal effect; these five are what couple
# cars to each other, and without them a full-field simulation is provably no more informative than a
# closed-form ranking of the pace prior.
alias P_OT_BIAS: Int = 17
alias P_OT_KPACE: Int = 18
alias P_MIN_FOLLOW: Int = 19
alias P_SC_BUNCH: Int = 20
alias P_STOP_JITTER: Int = 21
# Per-car per-race pace uncertainty. Measured, and the single largest term in the model: a regression
# of observed race pace on grid position over 2,525 car-races has R^2 = 0.338 and a residual sd of
# 0.952 s/lap. Per-lap noise cannot substitute -- 0.18 s/lap over 60 laps averages to 0.023 s/lap of
# pace uncertainty, 41x too small, which made grid near-perfect knowledge of race pace and collapsed
# simulated order churn to 0.8 positions against a measured 2.68.
alias P_PACE_SIGMA: Int = 22
# Neutralisation DURATION. Without these a safety car was a scattered set of single laps rather than a
# window, so there was nothing for a pit decision to exploit.
alias P_SC_DUR_MAX: Int = 23
alias P_VSC_DUR_MAX: Int = 24
# Tyre-age advantage in the pass model. The reference is
# P(pass) = sigma(A + k_p * delta_pace + k_t * delta_age) with k_t = 0.46, and WITHOUT the age term
# fresh rubber confers no passing advantage -- which means an undercut cannot work in the model at all,
# however correctly the pit loss is priced.
alias P_OT_KAGE: Int = 25
# The tyre CLIFF. The plan's lap-time model is f0 + delta*a + 1[a > k]*s*(a - k), and only the linear
# part was implemented. That is not a detail: a fuel-corrected linear slope of ~0.01 s/lap/lap means 25
# laps of tyre age costs 0.25 s/lap, which repays a ~22.8 s stop only after 91 laps. A board built on
# the linear term alone therefore recommends staying out for the entire race, whatever else is correct.
# Corpus, fuel-corrected: a knee near age 28-30 with a post-knee slope of order 0.06-0.16 s/lap/lap.
alias P_CLIFF_AGE: Int = 26
alias P_CLIFF_SLOPE: Int = 27
# RIVAL pit policy for the board. Only the focal car pitted, so over a 40-lap horizon nineteen rivals
# ran to the end on one set of tyres and reached ~20 laps past the cliff -- a 1.6 s/lap penalty they
# would never actually take. That inflates every boxing option, and it became a serious bias the moment
# the cliff was implemented. Rivals now stop when their tyres reach the cliff, released by a per-lap
# hazard so the field does not pit in unison. The plan calls for reporting sensitivity across plausible
# rival policies, which is why the trigger is a parameter rather than hardwired to P_CLIFF_AGE.
alias P_RIVAL_PIT_AGE: Int = 28
alias P_RIVAL_PIT_RATE: Int = 29
alias N_PARAMS: Int = 30

alias MAX_STOPS: Int = 5


struct StrategyBoard(Copyable, Movable):
    """Per-option aggregates. The replication matrix stays inside the engine."""

    var p_ahead: List[Float64]
    var delta_vs_stay: List[Float64]
    var ci_lo: List[Float64]
    var ci_hi: List[Float64]
    var expected_position: List[Float64]
    var p_win: List[Float64]
    var p_podium: List[Float64]
    var recommended: Int
    var verdict: Int
    var n_replications: Int
    var crn_variance_ratio: Float64

    fn __init__(
        out self,
        var p_ahead: List[Float64],
        var delta_vs_stay: List[Float64],
        var ci_lo: List[Float64],
        var ci_hi: List[Float64],
        var expected_position: List[Float64],
        var p_win: List[Float64],
        var p_podium: List[Float64],
        recommended: Int,
        verdict: Int,
        n_replications: Int,
        crn_variance_ratio: Float64,
    ):
        self.p_ahead = p_ahead^
        self.delta_vs_stay = delta_vs_stay^
        self.ci_lo = ci_lo^
        self.ci_hi = ci_hi^
        self.expected_position = expected_position^
        self.p_win = p_win^
        self.p_podium = p_podium^
        self.recommended = recommended
        self.verdict = verdict
        self.n_replications = n_replications
        self.crn_variance_ratio = crn_variance_ratio


fn default_contest_params() -> List[Float64]:
    """Reference defaults. Deterministic, zero-argument — also the probe for this module."""
    var p = List[Float64]()
    for _ in range(N_PARAMS):
        p.append(0.0)
    p[P_PIT_LOSS] = 21.0
    p[P_LAP_NOISE] = 0.18
    # PER-LAP retirement hazard: 0.165 of cars over a mean 61-lap race
    p[P_DNF_PROB] = 0.00273
    # events PER LAP: the corpus gives 1.09 SC events over a ~57-lap race, so 1.09/57
    p[P_SC_LAMBDA] = 0.0191
    p[P_SC_PACE_MULT] = 1.40
    p[P_SC_PIT_FACTOR] = 0.45
    p[P_VSC_LAMBDA] = 0.0082
    p[P_VSC_PACE_MULT] = 1.22
    p[P_VSC_PIT_FACTOR] = 0.65
    p[P_DIRTY_WINDOW] = 1.20
    p[P_DIRTY_LOSS] = 0.35
    p[P_FUEL_EFFECT] = 0.05
    p[P_DELTA_OUT] = 1.20
    p[P_DELTA_IN] = 0.60
    p[P_SIGMA_PIT] = 0.90
    p[P_EPSILON] = 0.02
    p[P_MARGIN] = 0.01
    # P_OT_BIAS is the per-lap pass logit at EQUAL pace inside the dirty-air window: -2.44 is about an
    # 8% chance per lap, which is why a car can sit behind a rival it matches for a whole stint.
    # P_OT_KPACE = 0.87 is the reference pace coefficient. P_SC_BUNCH is the delta-time queue gap a
    # safety car compresses the field to.
    p[P_OT_BIAS] = -2.44
    p[P_OT_KPACE] = 0.87
    p[P_MIN_FOLLOW] = 0.35
    p[P_SC_BUNCH] = 0.80
    p[P_STOP_JITTER] = 0.10
    p[P_PACE_SIGMA] = 0.952
    # Recalibrated against the corpus: 1.09 SC events/race of mean 3.17 laps (uniform 1..5 has mean 3),
    # 0.47 VSC events of mean 1.28 laps (uniform 1..2 has mean 1.5). The old 0.55 / 0.70 belonged to
    # the escalating per-lap hazard that produced roughly 2.6 scattered SC laps at the race end.
    p[P_SC_DUR_MAX] = 5.0
    p[P_VSC_DUR_MAX] = 2.0
    p[P_OT_KAGE] = 0.046
    p[P_CLIFF_AGE] = 28.0
    p[P_CLIFF_SLOPE] = 0.08
    p[P_RIVAL_PIT_AGE] = 28.0
    p[P_RIVAL_PIT_RATE] = 0.34
    return p^


fn option_service_round(option: Int) -> Int:
    """Lap offset from now at which the focal car boxes. -1 means it does not."""
    if option == OPT_BOX_NOW:
        return 0
    if option == OPT_BOX_1:
        return 1
    if option == OPT_BOX_2:
        return 2
    return -1


fn option_board(
    car_pace: List[Float64], car_deg: List[Float64], car_elapsed: List[Float64],
    car_age: List[Float64], car_active: List[Float64],
    focal: Int, rival: Int, laps_remaining: Int,
    params: List[Float64], n_reps: Int, n_boot: Int,
    master_seed: Int, scenario_id: Int,
) -> StrategyBoard:
    """Simulate all four options over a shared random world and return the board.

    car_elapsed is cumulative race time so far (s); ordering at the flag is by that total. car_active
    is 1.0 for a running car, 0.0 for one already retired.
    """
    var n_cars = len(car_pace)
    # Fail safe on a degenerate workload rather than returning NaN (invalid JSON, kills the SDK
    # transport) or a RECOMMENDED verdict from zero evidence. An empty board must abstain.
    if n_reps < 1 or n_boot < 1 or n_cars < 1 or focal < 0 or focal >= n_cars:
        var z = List[Float64]()
        var zc = List[Float64]()
        for _ in range(N_OPTIONS):
            z.append(0.0)
        for _ in range(n_cars):
            zc.append(0.0)
        return StrategyBoard(z.copy(), z.copy(), z.copy(), z.copy(), z.copy(), z.copy(), z.copy(),
                             OPT_STAY, VERDICT_INCONCLUSIVE, 0, 0.0)
    var ms = UInt64(master_seed)
    var sc = UInt64(scenario_id)

    var pit_loss = params[P_PIT_LOSS]
    var lap_noise = params[P_LAP_NOISE]

    # per-replication, per-option outcomes retained IN the engine so intervals can be paired.
    # Welford moments alone cannot support a percentile bootstrap over individual replications.
    var ahead = List[Float64]()
    var finish_pos = List[Float64]()
    for _ in range(n_reps * N_OPTIONS):
        ahead.append(0.0)
        finish_pos.append(0.0)

    # Hoisted out of the hot loop. wear_clamp was previously called once per car per lap per
    # replication per option -- 4*N*C*L calls for a value that never changes.
    var deg_c = List[Float64]()
    var base_pen = List[Float64]()
    for c in range(n_cars):
        deg_c.append(wear_clamp(car_deg[c]))
        # THE TYRE PENALTY ALREADY IN car_pace.
        #
        # car_pace is a MEASURED estimate -- in-race it is the car's own recent green-lap median -- so it
        # already contains whatever its current tyres are costing it. Adding the absolute
        # wear_penalty(age) on top double-counts that, and the double-count grows with age: a car at age
        # 35 was charged ~1.4 s/lap it was already being charged, which over 20 remaining laps is ~28 s
        # of phantom loss. Same error as the per-car form double-count, in the tyre term.
        #
        # It also broke what a stop is WORTH. Resetting age to 0 returned the car to car_pace, i.e. to
        # the pace it had on WORN tyres, so the model captured the pit loss but not the pace gain that
        # justifies paying it. Subtracting the baseline makes a fresh set genuinely faster by exactly
        # what the old set was costing.
        #
        # Pre-race car_age is 0, so the baseline is 0 and nothing changes there.
        base_pen.append(wear_penalty(
            wear_clamp(car_deg[c]), car_age[c], params[P_CLIFF_AGE], params[P_CLIFF_SLOPE]
        ))

    # NOTE the leading underscore on the closure. The inventory parser scans for `fn NAME(` and does
    # not track nesting, so a nested `@parameter fn worker` was picked up as a MODULE-LEVEL public
    # function. The generated dispatch then emitted `from contest_strategy import worker`, which does
    # not exist, and the failed import silently took the whole module off the callable surface --
    # every function in it returned function_not_registered. Underscore-prefixed names are skipped.
    #
    # Replications are independent, so they parallelise cleanly. Each worker owns PRIVATE buffers --
    # sharing them would race on regime/elapsed/age/alive -- and writes only to its own replication
    # slice of the outcome arrays, so no synchronisation is needed. Raw pointers because a captured
    # List cannot be mutated from a parallel closure.
    var n_workers = info.num_physical_cores()
    if n_workers < 1:
        n_workers = 1
    if n_workers > n_reps:
        n_workers = n_reps
    var chunk = (n_reps + n_workers - 1) // n_workers
    var ahead_p = ahead.unsafe_ptr()
    var pos_p = finish_pos.unsafe_ptr()
    var deg_p = deg_c.unsafe_ptr()
    var basepen_p = base_pen.unsafe_ptr()

    @parameter
    fn _worker(wid: Int):
        var lo = wid * chunk
        var hi = lo + chunk
        if hi > n_reps:
            hi = n_reps
        if lo >= hi:
            return

        var regime = List[Int]()
        for _ in range(laps_remaining):
            regime.append(0)
        var retire_at = List[Int]()
        var elapsed = List[Float64]()
        var age = List[Float64]()
        var alive = List[Bool]()
        var prev_e = List[Float64]()
        var form = List[Float64]()
        var order = List[Int]()
        var pit_now = List[Bool]()
        for _ in range(n_cars):
            retire_at.append(0)
            elapsed.append(0.0)
            age.append(0.0)
            alive.append(False)
            prev_e.append(0.0)
            form.append(0.0)
            order.append(0)
            pit_now.append(False)

        for rep in range(lo, hi):
            var r = UInt64(rep)

            # ── exogenous world, drawn ONCE and reused by every option ─────────────
            # regime per remaining lap: 0 green, 1 SC, 2 VSC. SC takes priority.
            # Neutralisations are EVENTS WITH A DURATION, not independent per-lap coin flips.
            #
            # Two errors were here. First the hazard read lambda / (laps_remaining - lap), which
            # escalates from 0.009 on lap 1 to 0.550 on the final lap and puts almost every safety car
            # at the end of the race. The reference form lambda / L_rem is a CONSTANT hazard over the
            # remaining distance, so the expected event count is lambda; L_rem is the distance at the
            # decision point, not a per-lap countdown. Second, each lap was drawn independently, which
            # scatters isolated SC laps instead of producing a contiguous window -- and a scattered
            # safety car contains no cheap-pit WINDOW, which is the entire strategic content of one.
            #
            # Corpus over 131 races: SC 1.09 events/race, mean duration 3.17 laps, max 10;
            # VSC 0.47 events/race, mean duration 1.28 laps. Hence the recalibrated lambdas.
            for k in range(laps_remaining):
                regime[k] = 0
            var sl = 0
            while sl < laps_remaining:
                var lp = UInt64(sl)
                var u_sc = rng_uniform(ms, sc, r, lp, GLOBAL_SENTINEL, PROCESS_SAFETY_CAR, 0)
                var u_vsc = rng_uniform(ms, sc, r, lp, GLOBAL_SENTINEL, PROCESS_VSC, 0)
                # PER-LAP hazard, with no dependence on how much race is left. Dividing by
                # laps_remaining instead made the hazard 1.09/4 = 0.27 per lap with four laps to run,
                # so a safety car became 68% likely over that stretch and a cheap neutralised stop
                # looked attractive with 21 s of pit loss unrecoverable -- caught by the directional
                # test that boxing must never win over so short a horizon. Incident rate is per lap of
                # racing; it does not rise because the race is nearly over.
                var fired = 0
                var dmax = 0.0
                if u_sc < params[P_SC_LAMBDA]:
                    fired = 1
                    dmax = params[P_SC_DUR_MAX]
                elif u_vsc < params[P_VSC_LAMBDA]:
                    fired = 2
                    dmax = params[P_VSC_DUR_MAX]
                if fired == 0:
                    sl += 1
                    continue
                var ud = rng_uniform(
                    ms, sc, r, lp, GLOBAL_SENTINEL,
                    PROCESS_SAFETY_CAR if fired == 1 else PROCESS_VSC, 1
                )
                var dur = 1 + Int(ud * dmax)
                if dur < 1:
                    dur = 1
                var stop = sl + dur
                if stop > laps_remaining:
                    stop = laps_remaining
                for k in range(sl, stop):
                    regime[k] = fired
                sl = stop

            # Retirement: TWO draws per car -- does it retire at all, and if so on which lap. The previous
            # form drew one uniform per car PER LAP, i.e. N*C*L draws to resolve an event that almost never
            # fires (N=4000, C=19, L=30 is 2.28M draws against 152k here, ~15x fewer). Coordinates stay
            # keyed so CRN is unaffected; draw_index 0 decides, 1 places.
            # Per-car race form, drawn ONCE per replication and therefore shared by all four options.
            # It belongs to the exogenous world: which car has the pace today does not depend on when
            # the focal car stops, so pairing it is what CRN is for.
            for c in range(n_cars):
                form[c] = params[P_PACE_SIGMA] * rng_normal(
                    ms, sc, r, 0, UInt64(c), PROCESS_CAR_FORM, 0
                )

            for c in range(n_cars):
                if car_active[c] <= 0.5:
                    retire_at[c] = 0
                    continue
                var u_ret = rng_uniform(ms, sc, r, 0, UInt64(c), PROCESS_RETIREMENT, 0)
                # PER-LAP hazard compounded over the remaining distance, not a flat probability.
                # A once-per-car draw independent of laps_remaining kept ~9.6% of cars retiring whether
                # 57 laps remained or 14, so it destroyed cars that were about to finish and did so
                # hardest LATE -- which is precisely where the oracle degraded against current running
                # order (BSS +0.454 at 25% distance falling to +0.422 at 75% while running order climbed
                # to +0.706). Corpus: 0.165 of cars retire over a mean 61 laps, a per-lap hazard of
                # 0.00273. Same error family as the safety-car hazard fixed earlier.
                var p_ret = 1.0 - exp(Float64(laps_remaining) * log(1.0 - params[P_DNF_PROB]))
                if u_ret < p_ret:
                    var u_lap = rng_uniform(ms, sc, r, 0, UInt64(c), PROCESS_RETIREMENT, 1)
                    var at = Int(u_lap * Float64(laps_remaining))
                    if at >= laps_remaining:
                        at = laps_remaining - 1
                    retire_at[c] = at
                else:
                    retire_at[c] = laps_remaining

            for opt in range(N_OPTIONS):
                var pit_at = option_service_round(opt)
                for c in range(n_cars):
                    elapsed[c] = car_elapsed[c]
                    age[c] = car_age[c]
                    alive[c] = car_active[c] > 0.5
                    order[c] = c
                for i in range(1, n_cars):
                    var j = i
                    while j > 0 and elapsed[order[j - 1]] > elapsed[order[j]]:
                        var tmp = order[j - 1]
                        order[j - 1] = order[j]
                        order[j] = tmp
                        j -= 1

                for lap in range(laps_remaining):
                    var lp = UInt64(lap)
                    var reg = regime[lap]
                    var pace_mult = 1.0
                    var pit_factor = 1.0
                    if reg == 1:
                        pace_mult = params[P_SC_PACE_MULT]
                        pit_factor = params[P_SC_PIT_FACTOR]
                    elif reg == 2:
                        pace_mult = params[P_VSC_PACE_MULT]
                        pit_factor = params[P_VSC_PIT_FACTOR]

                    for c in range(n_cars):
                        prev_e[c] = elapsed[c]
                        pit_now[c] = False

                    # Leader first, so a hold cascades into a queue. This is what makes TRAFFIC
                    # RELEASE a real cost: an undercut that emerges behind a slower car pays the
                    # dirty-air loss and cannot simply drive past, which is the whole reason the
                    # option contrast is not just an arithmetic comparison of pit loss against tyre
                    # delta.
                    var prev_alive = -1
                    for oi in range(n_cars):
                        var c = order[oi]
                        if not alive[c]:
                            continue
                        if lap >= retire_at[c]:
                            alive[c] = False
                            continue

                        var t = car_pace[c] + form[c] + wear_penalty(
                            deg_p[c], age[c], params[P_CLIFF_AGE], params[P_CLIFF_SLOPE]
                        ) - basepen_p[c]
                        # fuel: the car lightens as the race runs down
                        # PLUS, not minus. `laps_remaining - lap` is the fuel still to burn, so a
                        # heavy car early is SLOWER. Subtracting inverted the profile: the simulated
                        # car was ~3 s/lap quicker at the start than at the finish. Common across cars
                        # so it never reordered them, but it made early laps cheap and late laps dear,
                        # biasing the early-versus-late pit comparison the board exists to make.
                        # degradation_state.load_corrected_rate REMOVES this term to recover tyre state,
                        # so the generator has to add it or the two kernels disagree on the sign.
                        t += params[P_FUEL_EFFECT] * Float64(laps_remaining - lap)
                        # lap noise — shared across options at these coordinates
                        t += params[P_LAP_NOISE] * rng_normal(
                            ms, sc, r, lp, UInt64(c), PROCESS_LAP_NOISE, 0
                        )
                        t = t * pace_mult

                        # A rival whose tyres have reached the cliff stops too, released by a
                        # per-lap hazard so the field does not pit in unison, and only while enough
                        # distance remains to repay the loss.
                        var rival_pit = False
                        if c != focal and age[c] >= params[P_RIVAL_PIT_AGE] \
                                and laps_remaining - lap > 6:
                            var ur = rng_uniform(
                                ms, sc, r, lp, UInt64(c), PROCESS_PIT_SERVICE, 2
                            )
                            if ur < params[P_RIVAL_PIT_RATE]:
                                rival_pit = True
                        if rival_pit:
                            var rs = params[P_PIT_LOSS] * pit_factor
                            var ur2 = rng_uniform(
                                ms, sc, r, lp, UInt64(c), PROCESS_PIT_SERVICE, 3
                            )
                            if ur2 > 0.0 and ur2 < 1.0:
                                rs += -params[P_SIGMA_PIT] * log(ur2)
                            t += rs + params[P_DELTA_IN]
                            age[c] = 0.0

                        # focal car's option-specific stop
                        if c == focal and pit_at >= 0 and lap == pit_at:
                            var stationary = pit_loss * pit_factor
                            # right-tailed service time: a symmetric draw understates the slow-stop tail
                            # Exp(sigma) via inverse transform. An earlier form used
                            # -sigma * (1 - u) with an absolute value, which is UNIFORM on
                            # [0, sigma] -- bounded, thin-tailed, and exactly the understatement the
                            # comment above warns against.
                            #
                            # The right-tail evidence is DEVELOPMENT-SEASON ONLY: 116 stationary times
                            # over 2019-2024, median 2.8 s, p90 9.8 s, max 24.0 s, implied sigma 2.29.
                            # A p90/median ratio of 3.5 is not something a bounded uniform can produce.
                            # An earlier version of this comment cited a pooled sigma of 1.88 drawn from
                            # a sample the PitStop feed only publishes from 2025 -- the frozen final test
                            # season. The parameter value itself was never taken from it, but justifying
                            # a MODEL FORM with test-season data is still the test helping select the
                            # system, so the evidence was re-derived without it.
                            # CRN: keyed on the STOP ORDINAL (lap_id 0), never on the pit lap. The
                            # focal stop lap IS the option -- 0, 1 or 2 -- so keying on `lp` gave each
                            # box option an INDEPENDENT service draw: zero shared draws, correlation ~0,
                            # and a per-replication service difference of 1.28 s at sigma 0.9 (2.7 s at
                            # the fitted 1.88). That is unpaired noise injected into exactly the term
                            # the timing substitution decides on, which is what CRN exists to remove.
                            # The frozen CRN test could not see it: it only checks coordinates reached
                            # by MORE THAN ONE option, and these never were.
                            var u = rng_uniform(ms, sc, r, 0, UInt64(c), PROCESS_PIT_SERVICE, 0)
                            if u > 0.0 and u < 1.0:
                                stationary += -params[P_SIGMA_PIT] * log(u)
                            t += stationary + params[P_DELTA_IN]
                            age[c] = 0.0
                        elif c == focal and pit_at >= 0 and lap == pit_at + 1:
                            t += params[P_DELTA_OUT]
                            age[c] = age[c] + 1.0
                        elif not rival_pit:
                            age[c] = age[c] + 1.0

                        # Dirty air and the pass attempt. The uniform is drawn at coordinates shared
                        # by all four options, so the exogenous "how the moment fell" is paired; the
                        # OUTCOME still differs between options because the gap and the pace delta
                        # differ. That is the distinction Invariant 1 draws between paired exogenous
                        # randomness and divergent endogenous events.
                        var held = False
                        var pitting = (c == focal and pit_at >= 0 and lap == pit_at) or rival_pit
                        if pitting:
                            pit_now[c] = True
                        # see the oracle: a leader in its pit box neither dirties the air nor blocks
                        if prev_alive >= 0 and reg == 0 and not pitting \
                                and not pit_now[prev_alive]:
                            var gap = prev_e[c] - prev_e[prev_alive]
                            if gap >= 0.0 and gap < params[P_DIRTY_WINDOW]:
                                var ea = car_pace[prev_alive] + form[prev_alive] + wear_penalty(
                                    deg_p[prev_alive], age[prev_alive],
                                    params[P_CLIFF_AGE], params[P_CLIFF_SLOPE])
                                var ec = car_pace[c] + form[c] + wear_penalty(
                                    deg_p[c], age[c], params[P_CLIFF_AGE], params[P_CLIFF_SLOPE])
                                var pp = 1.0 / (1.0 + exp(-(
                                    params[P_OT_BIAS] + params[P_OT_KPACE] * (ea - ec)
                                    + params[P_OT_KAGE] * (age[prev_alive] - age[c])
                                )))
                                var uo = rng_uniform(
                                    ms, sc, r, lp, UInt64(c), PROCESS_OVERTAKE, 0
                                )
                                if uo >= pp:
                                    t += params[P_DIRTY_LOSS]
                                    held = True

                        var ne = prev_e[c] + t
                        if held:
                            var floor_e = elapsed[prev_alive] + params[P_MIN_FOLLOW]
                            if ne < floor_e:
                                ne = floor_e
                        elapsed[c] = ne
                        prev_alive = c

                    for i in range(1, n_cars):
                        var j = i
                        while j > 0 and elapsed[order[j - 1]] > elapsed[order[j]]:
                            var tmp = order[j - 1]
                            order[j - 1] = order[j]
                            order[j] = tmp
                            j -= 1

                    if reg == 1:
                        var lead = -1
                        for oi in range(n_cars):
                            var c = order[oi]
                            if not alive[c]:
                                continue
                            if lead < 0:
                                lead = c
                                continue
                            var g = elapsed[c] - elapsed[lead]
                            if g > params[P_SC_BUNCH]:
                                g = params[P_SC_BUNCH]
                            if g < 0.0:
                                g = 0.0
                            elapsed[c] = elapsed[lead] + g
                            lead = c

                # The FROZEN DNF rule: retired cars are placed behind all classified finishers, ordered
                # by laps completed and then by retirement time. Both branches previously required
                # alive[focal], so two retirements gave is_ahead = 0 whatever the laps completed, and
                # every retired car received the identical position 1 + n_alive. outcome_distribution already
                # implements the rule; this is the decision path, and the utility spec is not optional
                # on the path that produces the recommendation.
                var pos = 1
                for c in range(n_cars):
                    if c == focal:
                        continue
                    if alive[c] and alive[focal]:
                        if elapsed[c] < elapsed[focal]:
                            pos += 1
                    elif alive[c] and not alive[focal]:
                        pos += 1
                    elif not alive[c] and not alive[focal]:
                        # more laps is better; equal laps broken by the later retirement, then by index
                        if retire_at[c] > retire_at[focal]:
                            pos += 1
                        elif retire_at[c] == retire_at[focal] and c < focal:
                            pos += 1
                var idx = rep * N_OPTIONS + opt
                pos_p[idx] = Float64(pos)
                var is_ahead = 0.0
                if alive[focal] and not alive[rival]:
                    is_ahead = 1.0
                elif alive[focal] and alive[rival]:
                    if elapsed[focal] < elapsed[rival]:
                        is_ahead = 1.0
                elif not alive[focal] and not alive[rival]:
                    if retire_at[focal] > retire_at[rival]:
                        is_ahead = 1.0
                    elif retire_at[focal] == retire_at[rival] and focal < rival:
                        is_ahead = 1.0
                ahead_p[idx] = is_ahead

    parallelize[_worker](n_workers)

    # ── aggregates ────────────────────────────────────────────────────────────
    var p_ahead = List[Float64]()
    var exp_pos = List[Float64]()
    var p_win = List[Float64]()
    var p_pod = List[Float64]()
    for opt in range(N_OPTIONS):
        var sa = 0.0
        var sp = 0.0
        var w = 0.0
        var pd = 0.0
        for rep in range(n_reps):
            var idx = rep * N_OPTIONS + opt
            sa += ahead[idx]
            sp += finish_pos[idx]
            if finish_pos[idx] <= 1.0:
                w += 1.0
            if finish_pos[idx] <= 3.0:
                pd += 1.0
        var fn_reps = Float64(n_reps)
        p_ahead.append(sa / fn_reps)
        exp_pos.append(sp / fn_reps)
        p_win.append(w / fn_reps)
        p_pod.append(pd / fn_reps)

    var delta = List[Float64]()
    for opt in range(N_OPTIONS):
        delta.append(p_ahead[opt] - p_ahead[OPT_STAY])

    # ── joint bootstrap: resample whole replication ROWS, never per option ────
    # Per-option resampling would destroy the CRN pairing the whole design exists to create. The board
    # also SELECTS the largest of three contrasts, so marginal intervals overstate confidence; a
    # max-statistic gives family-wise coverage.
    var se = List[Float64]()
    for opt in range(N_OPTIONS):
        se.append(0.0)
    var boot_delta = List[Float64]()
    for _ in range(n_boot * N_OPTIONS):
        boot_delta.append(0.0)

    for b in range(n_boot):
        var sums = List[Float64]()
        for _ in range(N_OPTIONS):
            sums.append(0.0)
        for j in range(n_reps):
            var u = philox_word(
                ms, sc, UInt64(b), 0, GLOBAL_SENTINEL, PROCESS_BOOTSTRAP, UInt64(j)
            )
            var pick = Int(u % UInt64(n_reps))
            for opt in range(N_OPTIONS):
                sums[opt] += ahead[pick * N_OPTIONS + opt]
        var base = sums[OPT_STAY] / Float64(n_reps)
        for opt in range(N_OPTIONS):
            boot_delta[b * N_OPTIONS + opt] = sums[opt] / Float64(n_reps) - base

    for opt in range(N_OPTIONS):
        var m = 0.0
        for b in range(n_boot):
            m += boot_delta[b * N_OPTIONS + opt]
        m /= Float64(n_boot)
        var v = 0.0
        for b in range(n_boot):
            var d = boot_delta[b * N_OPTIONS + opt] - m
            v += d * d
        if n_boot > 1:
            v /= Float64(n_boot - 1)
        se[opt] = sqrt(v)

    # max-|t| across the three real contrasts, 90th percentile by counting
    var t_star = 0.0
    var target = Int(0.90 * Float64(n_boot))
    for _ in range(1):
        var lo = 0.0
        var hi = 20.0
        for _iter in range(40):
            var mid = 0.5 * (lo + hi)
            var cnt = 0
            for b in range(n_boot):
                var mx = 0.0
                for opt in range(1, N_OPTIONS):
                    if se[opt] > 0.0:
                        var tt = (boot_delta[b * N_OPTIONS + opt] - delta[opt]) / se[opt]
                        if tt < 0.0:
                            tt = -tt
                        if tt > mx:
                            mx = tt
                if mx <= mid:
                    cnt += 1
            if cnt >= target:
                hi = mid
            else:
                lo = mid
        t_star = hi

    var ci_lo = List[Float64]()
    var ci_hi = List[Float64]()
    for opt in range(N_OPTIONS):
        ci_lo.append(delta[opt] - t_star * se[opt])
        ci_hi.append(delta[opt] + t_star * se[opt])

    # ── abstention ────────────────────────────────────────────────────────────
    # The decision is BOX or STAY; which lap to box is a refinement of it. An earlier version required
    # the best option to be separated from the next-best by a margin, which made a clear "box" call read
    # INCONCLUSIVE whenever box-now and box+1 were both excellent and tied -- being unable to separate
    # two options that prescribe the SAME action is not a reason to abstain from that action.
    #
    # So the threshold test is against STAY, using the simultaneous interval:
    #   lower bound above epsilon      -> box; the edge is real and practically meaningful
    #   upper bound below epsilon      -> stay; we are confident boxing does not clear the bar
    #   interval straddles epsilon     -> INCONCLUSIVE; we genuinely cannot tell
    # Timing is then the earliest box option within `margin` of the best, because if the timings are
    # indistinguishable the earliest banks the gain soonest.
    var best_box = OPT_BOX_NOW
    for opt in range(OPT_BOX_NOW, N_OPTIONS):
        if delta[opt] > delta[best_box]:
            best_box = opt

    var eps = params[P_EPSILON]
    var verdict = VERDICT_INCONCLUSIVE
    var recommended = OPT_STAY
    if ci_lo[best_box] > eps:
        verdict = VERDICT_RECOMMENDED
        recommended = best_box
        for opt in range(OPT_BOX_NOW, best_box):
            # The substituted option must clear the SAME bar. Testing only the point-estimate margin let
            # a board recommend an option whose own lower simultaneous bound sat below epsilon -- 1.3% of
            # probed boards at the frozen eps = 0.02, worst case a bound of 0.0096 against a 2 pp bar.
            # Condition (1) of the frozen rule applies to whatever is recommended, not to whatever
            # happened to score highest.
            if (delta[best_box] - delta[opt]) <= params[P_MARGIN] and ci_lo[opt] > eps:
                recommended = opt
                break
    elif ci_hi[best_box] < eps:
        verdict = VERDICT_RECOMMENDED
        recommended = OPT_STAY

    # CRN diagnostic: paired contrast variance against the independent-sampling approximation.
    # Below 1.0 means pairing is buying precision.
    var vr = 1.0
    if se[OPT_BOX_NOW] > 0.0:
        var pa = p_ahead[OPT_BOX_NOW]
        var pb = p_ahead[OPT_STAY]
        var indep = (pa * (1.0 - pa) + pb * (1.0 - pb)) / Float64(n_reps)
        if indep > 0.0:
            vr = (se[OPT_BOX_NOW] * se[OPT_BOX_NOW]) / indep

    return StrategyBoard(
        p_ahead^, delta^, ci_lo^, ci_hi^, exp_pos^, p_win^, p_pod^,
        recommended, verdict, n_reps, vr,
    )


struct OracleBoard(Copyable, Movable):
    """Per-car finish-position distribution summary from a full-race simulation."""

    var p_win: List[Float64]
    var p_podium: List[Float64]
    var p_points: List[Float64]
    var expected_position: List[Float64]
    var modal_winner: Int
    var n_replications: Int
    var mean_displacement: Float64
    """E|finish - start| in positions, taken over the FULL position distribution rather than the mean
    rank -- averaging ranks first smooths the displacement away. The corpus measures 2.68 across 2,576
    car-races, so this is the direct check that the simulated field churns as much as real races do. A
    model that treats its pace prior as near-certain scores far below it."""

    fn __init__(
        out self, var p_win: List[Float64], var p_podium: List[Float64],
        var p_points: List[Float64], var expected_position: List[Float64],
        modal_winner: Int, n_replications: Int, mean_displacement: Float64,
    ):
        self.p_win = p_win^
        self.p_podium = p_podium^
        self.p_points = p_points^
        self.expected_position = expected_position^
        self.modal_winner = modal_winner
        self.n_replications = n_replications
        self.mean_displacement = mean_displacement


fn outcome_distribution(
    car_pace: List[Float64], car_deg: List[Float64], car_form_sigma: List[Float64],
    car_elapsed: List[Float64], car_age: List[Float64], car_active: List[Float64],
    car_stops: List[Float64], laps_remaining: Int, params: List[Float64],
    n_reps: Int, master_seed: Int, scenario_id: Int,
) -> OracleBoard:
    """Full-field race simulation returning per-car win/podium/points probabilities.

    The heavy path: N replications x C cars x L laps in ONE call, parallelised over replication chunks
    with private per-worker buffers.

    WHY THIS KERNEL MODELS INTERACTION, recorded because two earlier versions did not and the failure
    was invisible in every summary statistic except one.

    An earlier oracle advanced each car as an independent sum of lap times. Under that structure every
    differentiating term cancels: degradation was flat and tyre age evolved identically for all cars,
    fuel was common, stops were placed at even intervals so pit loss was a shared constant, and the
    safety car applied a common multiplier. After the shared regime factor the only thing separating
    cars was the pace prior plus noise, so finishing order was the order statistic of independent
    normals -- and a softmax over the same pace prior computes that in closed form. A Monte Carlo of a
    non-interacting model CANNOT beat a closed-form ranking of that model. Measuring it as
    statistically indistinguishable from a one-line grid softmax was arithmetic, not misfortune.

    So the informative content lives entirely in the three couplings below:

      * DIRTY AIR AND OVERTAKING. A car within P_DIRTY_WINDOW of the car ahead attempts a pass with
        probability sigma(P_OT_BIAS + P_OT_KPACE * pace advantage); failing, it loses P_DIRTY_LOSS and
        is held no closer than P_MIN_FOLLOW behind. The field is walked LEADER FIRST so the hold
        cascades and a queue forms. This is what makes track position worth more than raw pace.
      * SAFETY-CAR BUNCHING. A real safety car COMPRESSES the field to a delta-time queue. A pace
        multiplier alone does the opposite -- it scales every gap up, so the slower car loses
        proportionally more. Bunching is the strategically decisive half, and it is a shared shock with
        heterogeneous, strategy-dependent impact, which no per-car marginal can express.
      * PER-CAR STOP LAPS. Stop laps are jittered per car and per replication, so undercuts, overcuts
        and pit-window traffic actually occur instead of cancelling.

    The corpus is the check on all three: real finishing order churns a mean of 2.68 positions against
    the opening lap. A free-reordering lap-time-sum model churns far more, so the blocking mechanism is
    not a refinement -- it is what reproduces the persistence that real races show.

    Retirement, safety-car and lap-noise draws use the same keyed coordinates as option_board, so an
    oracle run and a board run over the same scenario_id share one random world.
    """
    var n_cars = len(car_pace)
    var ms = UInt64(master_seed)
    var sc = UInt64(scenario_id)

    # A degenerate replication count must FAIL SAFE, not crash a shared worker. n_reps = 0 divided by
    # zero and returned NaN, which serialises as a bare `nan` token -- invalid JSON, so the SDK transport
    # died with a decode error; n_reps < 0 crashed the process with SIGTRAP, taking every other caller on
    # that worker with it. The metrics and search kernels already clamp degenerate scalars, so this was an
    # asymmetry rather than a policy.
    if n_reps < 1 or n_cars < 1:
        var z = List[Float64]()
        for _ in range(n_cars):
            z.append(0.0)
        return OracleBoard(z.copy(), z.copy(), z.copy(), z.copy(), 0, 0, 0.0)
    # Same fail-safe for the SHAPE contract: every per-car array must cover all n_cars, and
    # params must carry the full calibrated vector (indices run to P_RIVAL_PIT_RATE = 29).
    # A short read below aborts the worker (uncatchable), e.g. params[26] on a 5-element list.
    if (
        len(car_deg) < n_cars or len(car_form_sigma) < n_cars or len(car_elapsed) < n_cars
        or len(car_age) < n_cars or len(car_active) < n_cars or len(car_stops) < n_cars
        or len(params) <= P_RIVAL_PIT_RATE
    ):
        var z = List[Float64]()
        for _ in range(n_cars):
            z.append(0.0)
        return OracleBoard(z.copy(), z.copy(), z.copy(), z.copy(), 0, 0, 0.0)

    var deg_c = List[Float64]()
    var base_pen = List[Float64]()
    for c in range(n_cars):
        deg_c.append(wear_clamp(car_deg[c]))
        # THE TYRE PENALTY ALREADY IN car_pace.
        #
        # car_pace is a MEASURED estimate -- in-race it is the car's own recent green-lap median -- so it
        # already contains whatever its current tyres are costing it. Adding the absolute
        # wear_penalty(age) on top double-counts that, and the double-count grows with age: a car at age
        # 35 was charged ~1.4 s/lap it was already being charged, which over 20 remaining laps is ~28 s
        # of phantom loss. Same error as the per-car form double-count, in the tyre term.
        #
        # It also broke what a stop is WORTH. Resetting age to 0 returned the car to car_pace, i.e. to
        # the pace it had on WORN tyres, so the model captured the pit loss but not the pace gain that
        # justifies paying it. Subtracting the baseline makes a fresh set genuinely faster by exactly
        # what the old set was costing.
        #
        # Pre-race car_age is 0, so the baseline is 0 and nothing changes there.
        base_pen.append(wear_penalty(
            wear_clamp(car_deg[c]), car_age[c], params[P_CLIFF_AGE], params[P_CLIFF_SLOPE]
        ))

    var n_workers = info.num_physical_cores()
    if n_workers < 1:
        n_workers = 1
    if n_workers > n_reps:
        n_workers = n_reps
    var chunk = (n_reps + n_workers - 1) // n_workers

    # PER-WORKER histogram slabs, reduced after the parallel region. A single shared histogram is a
    # DATA RACE: `hist[cell] += 1` from concurrent workers loses updates, which showed up as p_win
    # summing to 0.9915 instead of 1.0 -- about 0.85% of increments silently dropped. The board does not
    # hit this because each worker writes to its own replication slice; a histogram is shared by
    # construction. Diagnosed only because the probabilities had to sum to exactly one.
    # start position = rank by elapsed race time at the snapshot, so the churn diagnostic is defined
    # from the kernel's own inputs rather than an assumed car ordering.
    var start_rank = List[Float64]()
    for c in range(n_cars):
        var rk = 1
        for d in range(n_cars):
            if d != c and (car_elapsed[d] < car_elapsed[c]
                           or (car_elapsed[d] == car_elapsed[c] and d < c)):
                rk += 1
        start_rank.append(Float64(rk))

    var slab = n_cars * n_cars
    var pos_hist = List[Float64]()
    for _ in range(n_workers * slab):
        pos_hist.append(0.0)
    var hist_p = pos_hist.unsafe_ptr()
    var deg_p = deg_c.unsafe_ptr()
    var basepen_p = base_pen.unsafe_ptr()

    @parameter
    fn _oracle_worker(wid: Int):
        var lo = wid * chunk
        var hi = lo + chunk
        if hi > n_reps:
            hi = n_reps
        if lo >= hi:
            return
        var regime = List[Int]()
        for _ in range(laps_remaining):
            regime.append(0)
        var retire_at = List[Int]()
        var elapsed = List[Float64]()
        var age = List[Float64]()
        var alive = List[Bool]()
        var laps_done = List[Int]()
        var prev_e = List[Float64]()
        var form = List[Float64]()
        var order = List[Int]()
        var pit_now = List[Bool]()
        var stop_at = List[Int]()
        for _ in range(n_cars):
            retire_at.append(0)
            elapsed.append(0.0)
            age.append(0.0)
            alive.append(False)
            laps_done.append(0)
            prev_e.append(0.0)
            form.append(0.0)
            order.append(0)
            pit_now.append(False)
        for _ in range(n_cars * MAX_STOPS):
            stop_at.append(-1)

        for rep in range(lo, hi):
            var r = UInt64(rep)
            # Neutralisations are EVENTS WITH A DURATION, not independent per-lap coin flips.
            #
            # Two errors were here. First the hazard read lambda / (laps_remaining - lap), which
            # escalates from 0.009 on lap 1 to 0.550 on the final lap and puts almost every safety car
            # at the end of the race. The reference form lambda / L_rem is a CONSTANT hazard over the
            # remaining distance, so the expected event count is lambda; L_rem is the distance at the
            # decision point, not a per-lap countdown. Second, each lap was drawn independently, which
            # scatters isolated SC laps instead of producing a contiguous window -- and a scattered
            # safety car contains no cheap-pit WINDOW, which is the entire strategic content of one.
            #
            # Corpus over 131 races: SC 1.09 events/race, mean duration 3.17 laps, max 10;
            # VSC 0.47 events/race, mean duration 1.28 laps. Hence the recalibrated lambdas.
            for k in range(laps_remaining):
                regime[k] = 0
            var sl = 0
            while sl < laps_remaining:
                var lp = UInt64(sl)
                var u_sc = rng_uniform(ms, sc, r, lp, GLOBAL_SENTINEL, PROCESS_SAFETY_CAR, 0)
                var u_vsc = rng_uniform(ms, sc, r, lp, GLOBAL_SENTINEL, PROCESS_VSC, 0)
                # PER-LAP hazard, with no dependence on how much race is left. Dividing by
                # laps_remaining instead made the hazard 1.09/4 = 0.27 per lap with four laps to run,
                # so a safety car became 68% likely over that stretch and a cheap neutralised stop
                # looked attractive with 21 s of pit loss unrecoverable -- caught by the directional
                # test that boxing must never win over so short a horizon. Incident rate is per lap of
                # racing; it does not rise because the race is nearly over.
                var fired = 0
                var dmax = 0.0
                if u_sc < params[P_SC_LAMBDA]:
                    fired = 1
                    dmax = params[P_SC_DUR_MAX]
                elif u_vsc < params[P_VSC_LAMBDA]:
                    fired = 2
                    dmax = params[P_VSC_DUR_MAX]
                if fired == 0:
                    sl += 1
                    continue
                var ud = rng_uniform(
                    ms, sc, r, lp, GLOBAL_SENTINEL,
                    PROCESS_SAFETY_CAR if fired == 1 else PROCESS_VSC, 1
                )
                var dur = 1 + Int(ud * dmax)
                if dur < 1:
                    dur = 1
                var stop = sl + dur
                if stop > laps_remaining:
                    stop = laps_remaining
                for k in range(sl, stop):
                    regime[k] = fired
                sl = stop

            for c in range(n_cars):
                elapsed[c] = car_elapsed[c]
                age[c] = car_age[c]
                alive[c] = car_active[c] > 0.5
                laps_done[c] = 0
                # PER-CAR form uncertainty, drawn once per replication and held for the whole race.
                #
                # A single global sigma is only right BEFORE the start. In-race the pace estimate
                # already CONTAINS the car\'s form -- it was measured from that car\'s own green laps --
                # so drawing the pre-race sigma on top double-counts it and re-randomises a field that
                # reality has largely settled. Measured consequence: against current running order the
                # oracle scored BSS +0.476 at 25% distance (a tie) but +0.424 against +0.706 at 75%,
                # getting WORSE as the race progressed, exactly as a model injecting a full race of
                # unknown form into a nearly-decided order would.
                #
                # The caller therefore supplies the standard error of each car\'s pace estimate:
                # sigma_lap / sqrt(observed green laps) in-race, and the calibrated pre-race sigma at
                # lights out.
                form[c] = car_form_sigma[c] * rng_normal(
                    ms, sc, r, 0, UInt64(c), PROCESS_CAR_FORM, 0
                )
                if car_active[c] <= 0.5:
                    retire_at[c] = 0
                    continue
                var u_ret = rng_uniform(ms, sc, r, 0, UInt64(c), PROCESS_RETIREMENT, 0)
                # PER-LAP hazard compounded over the remaining distance, not a flat probability.
                # A once-per-car draw independent of laps_remaining kept ~9.6% of cars retiring whether
                # 57 laps remained or 14, so it destroyed cars that were about to finish and did so
                # hardest LATE -- which is precisely where the oracle degraded against current running
                # order (BSS +0.454 at 25% distance falling to +0.422 at 75% while running order climbed
                # to +0.706). Corpus: 0.165 of cars retire over a mean 61 laps, a per-lap hazard of
                # 0.00273. Same error family as the safety-car hazard fixed earlier.
                var p_ret = 1.0 - exp(Float64(laps_remaining) * log(1.0 - params[P_DNF_PROB]))
                if u_ret < p_ret:
                    var u_lap = rng_uniform(ms, sc, r, 0, UInt64(c), PROCESS_RETIREMENT, 1)
                    var at = Int(u_lap * Float64(laps_remaining))
                    if at >= laps_remaining:
                        at = laps_remaining - 1
                    retire_at[c] = at
                else:
                    retire_at[c] = laps_remaining

            # Per-car stop laps: even-interval targets with a keyed jitter. With IDENTICAL stop laps
            # the pit loss is a common offset that cancels exactly across the field, so the pit and
            # tyre terms contributed nothing to ordering. The corpus puts real stops across 0.12-0.79
            # of race distance, nowhere near a single lap.
            for c in range(n_cars):
                var ns = Int(car_stops[c])
                if ns < 0:
                    ns = 0
                if ns > MAX_STOPS:
                    ns = MAX_STOPS
                for k in range(MAX_STOPS):
                    stop_at[c * MAX_STOPS + k] = -1
                for k in range(1, ns + 1):
                    var frac = Float64(k) / Float64(ns + 1)
                    var uj = rng_uniform(ms, sc, r, UInt64(k), UInt64(c), PROCESS_PIT_SERVICE, 1)
                    var at = Int((frac + (uj - 0.5) * 2.0 * params[P_STOP_JITTER])
                                 * Float64(laps_remaining))
                    if at < 1:
                        at = 1
                    # Strictly increasing. At a jitter wide enough for two targets to collide, the
                    # flag-based lookup below fires ONCE, so the car silently performs fewer stops than
                    # the plan called for -- and the search would have been free to exploit that as a
                    # way to make stops cheap.
                    if k > 1:
                        var prior = stop_at[c * MAX_STOPS + (k - 2)]
                        if at <= prior:
                            at = prior + 1
                    if at > laps_remaining - 1:
                        at = laps_remaining - 1
                    stop_at[c * MAX_STOPS + (k - 1)] = at

            # running order, leader first
            for c in range(n_cars):
                order[c] = c
            for i in range(1, n_cars):
                var j = i
                while j > 0 and elapsed[order[j - 1]] > elapsed[order[j]]:
                    var tmp = order[j - 1]
                    order[j - 1] = order[j]
                    order[j] = tmp
                    j -= 1

            for lap in range(laps_remaining):
                var lp = UInt64(lap)
                var reg = regime[lap]
                var pace_mult = 1.0
                var pit_factor = 1.0
                if reg == 1:
                    pace_mult = params[P_SC_PACE_MULT]
                    pit_factor = params[P_SC_PIT_FACTOR]
                elif reg == 2:
                    pace_mult = params[P_VSC_PACE_MULT]
                    pit_factor = params[P_VSC_PIT_FACTOR]
                for c in range(n_cars):
                    prev_e[c] = elapsed[c]
                    pit_now[c] = False

                # LEADER FIRST, so a hold cascades into a queue: a blocked car is kept behind the car
                # ahead's NEW time, and the next car back is then kept behind that. Walking in car-index
                # order instead would make blocking a per-car effect rather than a field effect.
                var prev_alive = -1
                for pos in range(n_cars):
                    var c = order[pos]
                    if not alive[c]:
                        continue
                    if lap >= retire_at[c]:
                        alive[c] = False
                        continue
                    var t = car_pace[c] + form[c] + wear_penalty(
                        deg_p[c], age[c], params[P_CLIFF_AGE], params[P_CLIFF_SLOPE]
                    ) - basepen_p[c]
                    t += params[P_FUEL_EFFECT] * Float64(laps_remaining - lap)
                    t += params[P_LAP_NOISE] * rng_normal(
                        ms, sc, r, lp, UInt64(c), PROCESS_LAP_NOISE, 0
                    )
                    t = t * pace_mult

                    # dirty air and the pass attempt, against the nearest car ahead ON TRACK. Suspended
                    # under a neutralisation, where overtaking is forbidden.
                    # A leader that has just peeled into the pit lane is no longer in front, so it
                    # neither dirties the air nor blocks. Without this the model held a car behind a
                    # rival that was stationary in its pit box -- which inverts the undercut: the
                    # follower should be RELEASED into clean air, and that release is precisely the
                    # gain an undercut is trying to capture.
                    var pitting = False
                    var out_lap = False
                    for k in range(MAX_STOPS):
                        if stop_at[c * MAX_STOPS + k] == lap:
                            pitting = True
                        if stop_at[c * MAX_STOPS + k] == lap - 1:
                            out_lap = True

                    # `not pitting` matches option_board. Without it the oracle charged P_DIRTY_LOSS
                    # (fitted 0.537 s, not the 0.35 default) to a car peeling into the pit lane while the
                    # board did not, so the two priced a stop up to half a second apart -- the same defect
                    # class as the P_DELTA_OUT omission fixed earlier, and the plan requires the optimizer
                    # and the simulator to price a stop identically.
                    var held = False
                    if prev_alive >= 0 and reg == 0 and not pit_now[prev_alive] and not pitting:
                        var gap = prev_e[c] - prev_e[prev_alive]
                        if gap >= 0.0 and gap < params[P_DIRTY_WINDOW]:
                            # EFFECTIVE pace, not the prior: form and current tyre state are what the
                            # cars actually have today. Using car_pace alone meant a car on fresh
                            # rubber with strong form passed no more readily than one on dead tyres.
                            var ea = car_pace[prev_alive] + form[prev_alive] + wear_penalty(
                                deg_p[prev_alive], age[prev_alive],
                                params[P_CLIFF_AGE], params[P_CLIFF_SLOPE])
                            var ec = car_pace[c] + form[c] + wear_penalty(
                                deg_p[c], age[c], params[P_CLIFF_AGE], params[P_CLIFF_SLOPE])
                            var pp = 1.0 / (1.0 + exp(-(
                                params[P_OT_BIAS] + params[P_OT_KPACE] * (ea - ec)
                                + params[P_OT_KAGE] * (age[prev_alive] - age[c])
                            )))
                            var uo = rng_uniform(ms, sc, r, lp, UInt64(c), PROCESS_OVERTAKE, 0)
                            if uo >= pp:
                                t += params[P_DIRTY_LOSS]
                                held = True

                    if out_lap:
                        # Out-lap warm-up. The board charged this and the oracle did not, so the
                        # oracle under-priced every stop by P_DELTA_OUT. The plan requires the two to
                        # price a stop identically or the engine drifts toward recommending a pit.
                        t += params[P_DELTA_OUT]
                    if pitting:
                        var stationary = params[P_PIT_LOSS] * pit_factor
                        var u = rng_uniform(ms, sc, r, lp, UInt64(c), PROCESS_PIT_SERVICE, 0)
                        if u > 0.0 and u < 1.0:
                            var tail = -params[P_SIGMA_PIT] * log(u)
                            stationary += tail
                        t += stationary + params[P_DELTA_IN]
                        age[c] = 0.0
                        pit_now[c] = True
                        # a car peeling into the pits is no longer held by the car ahead
                        held = False
                    else:
                        age[c] = age[c] + 1.0

                    var ne = prev_e[c] + t
                    if held:
                        var floor_e = elapsed[prev_alive] + params[P_MIN_FOLLOW]
                        if ne < floor_e:
                            ne = floor_e
                    elapsed[c] = ne
                    laps_done[c] = laps_done[c] + 1
                    prev_alive = c

                # re-sort; the order is nearly sorted between laps so insertion sort is ~O(C).
                # Retired cars stop accumulating and drift to the front, where the alive check skips
                # them.
                for i in range(1, n_cars):
                    var j = i
                    while j > 0 and elapsed[order[j - 1]] > elapsed[order[j]]:
                        var tmp = order[j - 1]
                        order[j - 1] = order[j]
                        order[j] = tmp
                        j -= 1

                # Safety-car bunching, applied AFTER the re-sort so the queue forms on the true order.
                # This is the half that changes what a pit stop is worth, and it is a shared shock whose
                # impact depends on each car's strategy state -- not expressible as a per-car marginal.
                if reg == 1:
                    var lead = -1
                    for pos in range(n_cars):
                        var c = order[pos]
                        if not alive[c]:
                            continue
                        if lead < 0:
                            lead = c
                            continue
                        var g = elapsed[c] - elapsed[lead]
                        if g > params[P_SC_BUNCH]:
                            g = params[P_SC_BUNCH]
                        if g < 0.0:
                            g = 0.0
                        elapsed[c] = elapsed[lead] + g
                        lead = c

            # Classify into a STRICT TOTAL ORDER. The frozen utility places retired cars behind all
            # classified finishers, ordered by laps completed then retirement time; ties on both need a
            # final deterministic break or ranks are not a permutation and p_win does not sum to 1.
            # An earlier version omitted the retirement-time and index breaks and summed to 0.991,
            # because two retired cars with equal laps could both claim the same rank.
            for c in range(n_cars):
                var rank = 1
                for d in range(n_cars):
                    if d == c:
                        continue
                    var d_better = False
                    if alive[d] and not alive[c]:
                        d_better = True
                    elif alive[d] == alive[c]:
                        if alive[c]:
                            if elapsed[d] < elapsed[c]:
                                d_better = True
                            elif elapsed[d] == elapsed[c] and d < c:
                                d_better = True
                        else:
                            if laps_done[d] > laps_done[c]:
                                d_better = True
                            elif laps_done[d] == laps_done[c]:
                                if retire_at[d] > retire_at[c]:
                                    d_better = True
                                elif retire_at[d] == retire_at[c] and d < c:
                                    d_better = True
                    if d_better:
                        rank += 1
                hist_p[wid * slab + c * n_cars + (rank - 1)] += 1.0

    parallelize[_oracle_worker](n_workers)

    # reduce the slabs
    for w in range(1, n_workers):
        for k in range(slab):
            pos_hist[k] = pos_hist[k] + pos_hist[w * slab + k]

    var p_win = List[Float64]()
    var p_pod = List[Float64]()
    var p_pts = List[Float64]()
    var e_pos = List[Float64]()
    var disp = 0.0
    var fn_reps = Float64(n_reps)
    var best = 0
    var best_p = -1.0
    for c in range(n_cars):
        var w = pos_hist[c * n_cars] / fn_reps
        var pod = 0.0
        var pts = 0.0
        var ep = 0.0
        for k in range(n_cars):
            var f = pos_hist[c * n_cars + k] / fn_reps
            if k < 3:
                pod += f
            if k < 10:
                pts += f
            ep += f * Float64(k + 1)
            var d = Float64(k + 1) - start_rank[c]
            if d < 0.0:
                d = -d
            disp += f * d
        p_win.append(w)
        p_pod.append(pod)
        p_pts.append(pts)
        e_pos.append(ep)
        if w > best_p:
            best_p = w
            best = c
    return OracleBoard(p_win^, p_pod^, p_pts^, e_pos^, best, n_reps, disp / Float64(n_cars))


fn contest_worker_count() -> Int:
    """Cores the parallel path will actually use. Deterministic, zero-argument.

    Exists because the compiled binary ran ~8.7x slower than JIT, and the first thing to rule out was
    whether the worker count differs inside the server process.
    """
    var n = info.num_physical_cores()
    if n < 1:
        n = 1
    return n


fn contest_strategy_version() -> String:
    """Contract identifier. Deterministic, zero-argument."""
    return String("contest-strategy-crn/v1")
