"""test_strategy_crn.mojo — known-value tests for the common-random-numbers harness.

Hand-written. Nothing here is this module agreeing with itself: every scenario draw is asserted
BIT-FOR-BIT against the frozen `determinism.counter_rng` called directly at the coordinates
`strat_crn_contract()` claims, every payoff is asserted against a sum re-derived from those frozen
draws, and every act count is asserted against a count re-derived from the frozen
`rng_bernoulli`. A test that only checked a mean would pass with the coordinates permuted.

THE TWO ASSERTIONS THIS PACKAGE EXISTS FOR
==========================================

1. TWO POLICIES AT THE SAME SEED SEE BIT-IDENTICAL SCENARIOS — compared as RAW DRAWS, not as
   summary statistics. `crn_scenario_tape` is called twice at identical coordinates and every
   cell is compared with `==`; `crn_scenario_digest` folds the raw IEEE-754 bits so agreement to
   the last mantissa bit is what is being asserted. `crn_pairing_audit` does the same inside the
   driver on all 32 scenarios and reports `n_scenarios_bit_identical`, which is asserted to be 32.

2. THE PAIRED DIFFERENCE HAS STRICTLY LOWER VARIANCE THAN THE UNPAIRED ONE. MEASURED, both
   numbers printed, on one problem: seed 12345, family 7, 32 scenarios, a 64-step undiscounted
   horizon, one uniform(0,1) factor, act cost 0.5, threshold policies 0.40 and 0.50.

       PAIRED   mean 0.33597126582607956   variance 0.016154113656956768   p = 1.01e-15
       UNPAIRED mean 0.25119989823076510   variance 2.812071595342685      p = 0.403
       variance ratio unpaired / paired = 174.07773989083373

   The paired 95% interval is [0.290, 0.382] and EXCLUDES zero; the unpaired one is
   [-0.353, 0.856] and CONTAINS it. Identical work, identical seed, opposite conclusions —
   `conclusions_differ` is asserted True. The unpaired comparison cannot rank two policies that
   the paired one separates at p = 1e-15.

   Why this problem: with one uniform(0,1) factor and cost 0.5 the exact per-step expected payoff
   of threshold `theta` is `integral_theta^1 (x - 0.5) dx = (1 - theta^2)/2 - 0.5(1 - theta)`,
   so 0.40 gives 0.120 and 0.50 gives 0.125 — a 0.005-per-step effect against a per-step standard
   deviation of 0.166. Small relative to scenario noise is exactly where pairing decides the
   comparison, and it is the regime a benchmark that only reported "the better policy won" would
   never test.

"NO SIGNIFICANT DIFFERENCE" IS A VALUE HERE, NOT A MISSING WINNER
================================================================
Two constructions, both asserted:

  * the EXACT tie by reparameterisation. `w = [1.0], theta = 0.40` and `w = [2.0], theta = 0.80`
    are different parameter rows that make the identical decision at every step, because
    `2x >= 0.8` and `x >= 0.4` are the same predicate and `2 * 0.4` is exactly `0.8` in binary.
    The paired difference is identically zero at every scenario: `paired_mean == 0.0`,
    `paired_variance == 0.0`, `paired_p_value == 1.0`, `paired_excludes_zero == False`. Not a coin
    flip and not an absence — a stated verdict of no difference. `has_variance_ratio` is asserted
    FALSE, because the ratio would be infinite and an infinity is not a number a caller can store.
  * the EXACT tie by duplication (two identical rows), which must give the same answer.

And the STATISTICAL tie, which is the harder honest case: `theta = 0.40` versus `theta = 0.60`
have EQUAL exact expectations (both 0.12 per step, by the same integral), so the true difference
is zero and the estimator is a random variable around it. MEASURED:

    n = 200   paired mean 0.03375   |t| = 2.378   p = 0.0183   95% CI [0.0058, 0.0617]
    n = 500   paired mean 0.00509   |t| = 0.565   p = 0.5721   95% CI [-0.0126, 0.0228]

At 200 scenarios the 95% interval EXCLUDES zero for a pair of policies that are exactly tied.
That is not hidden here: it is printed, and it is the reason a ranking must carry its interval
rather than emit a winner. The assertion is a stated 3-sigma band (|t| <= 3, a two-sided normal
tail of 0.0027), which both runs satisfy — 2.378 and 0.565 — and which is deterministic at a
fixed seed rather than a probabilistic hope.

INDEPENDENCE ACROSS SCENARIOS IS MEASURED, NOT TRUSTED
=====================================================
A counter-based generator gives independent replications by construction. Asserted anyway, over
DISJOINT pairs so no draw appears on both sides. Seed 999, family 3, 512 scenarios of a 64-step
two-factor tape:

    lag 1   256 scenario pairs   32768 draw pairs   r =  0.001233   z =  0.223
    lag 2   170 scenario pairs   21760 draw pairs   r =  0.006220   z =  0.918
    lag 1, standard normal factors                 r = -0.009784   z = -1.771

The pair counts are hand-derived: at stride `lag + 1`, pair `i` uses scenarios
`i*(lag+1)` and `i*(lag+1)+lag`, so lag 1 gives the 256 pairs with `2i+1 < 512` and lag 2 the 170
with `3i+2 < 512`. The correlation is computed by the FROZEN `math_ext.correlation`.

THE WORK CHARGE IS ASSERTED TO BE ABLE TO REFUSE
================================================
`crn_request_status(2, 2048, 2048, 1, ...)` is accepted while
`crn_pairing_audit(..., 2048 scenarios, 2048 steps, ...)` is refused with
`work_budget_exceeded` — because the audit deliberately builds THREE tape sets and charges for
them. A charge that could not refuse anything would not be a charge.

NO REFUSED INPUT ABORTS THE WORKER
==================================
Reading past a `List` end in Mojo is an UNCATCHABLE bounds assertion that takes the whole process,
and `try`/`except` does not help. Every count-versus-length trap is exercised — `n_strategies = 5`
against a 3-element parameter block, `horizon = 99` against a 3-cell tape, `strategy = 7` of 3,
`strategy = -1` — and each returns a typed status. The suite REACHING its own summary line is the
proof: if any of them aborted, this file would print nothing at all.
"""
from std.math import sqrt

from determinism.counter_rng import (
    rng_bernoulli,
    rng_exponential,
    rng_normal,
    rng_uniform,
)
from determinism.streams import stream_id

from strategy.contract import (
    STRAT_ERR_ACTION_RANGE,
    STRAT_ERR_DIMENSION_TOO_LARGE,
    STRAT_ERR_DISCOUNT_RANGE,
    STRAT_ERR_FACTOR_RANGE,
    STRAT_ERR_HORIZON_RANGE,
    STRAT_ERR_LEVEL_RANGE,
    STRAT_ERR_NON_FINITE,
    STRAT_ERR_NOT_EVALUABLE,
    STRAT_ERR_POLICY_ARITY,
    STRAT_ERR_POLICY_KIND,
    STRAT_ERR_PROBABILITY,
    STRAT_ERR_SCENARIO_RANGE,
    STRAT_ERR_SEED_RANGE,
    STRAT_ERR_SHAPE,
    STRAT_ERR_TOO_FEW_REPLICATIONS,
    STRAT_ERR_TOO_FEW_STRATEGIES,
    STRAT_ERR_WORK_BUDGET,
    STRAT_FACTOR_BERNOULLI,
    STRAT_FACTOR_EXPONENTIAL,
    STRAT_FACTOR_NORMAL,
    STRAT_FACTOR_UNIFORM,
    STRAT_OK,
    STRAT_POLICY_CONSTANT,
    STRAT_POLICY_MIXED,
    STRAT_POLICY_TABULAR,
    STRAT_POLICY_THRESHOLD,
    strat_crn_contract,
    strat_rng_version,
)
from strategy.crn import (
    crn_cell_draw,
    crn_contract_id,
    crn_environment_id,
    crn_evaluate_on_tape,
    crn_evaluate_policies,
    crn_evaluate_policy,
    crn_generator_version,
    crn_independence_audit,
    crn_pairing_audit,
    crn_policy_arity,
    crn_policy_stream,
    crn_request_status,
    crn_scenario_digest,
    crn_scenario_stream,
    crn_scenario_tape,
)

# The digest of the tape at (seed 7, family 3, scenario 5, horizon 4, 2 uniform factors), folded
# bit-exactly by `strat_crn_fold`. A GOLDEN value: it changes if the Philox layout changes, if any
# coordinate of the assignment moves, or if the row-major cell order changes. 62-bit masked, so it
# is never negative and never confusable with the -1 that means "no tape".
comptime GOLDEN_DIGEST_S5: Int = 3574067134758508816
comptime GOLDEN_DIGEST_S6: Int = 940645111454183288

# The frozen Bernoulli(0.7) act counts on the POLICY stream for strategies 0 and 1 over 8
# scenarios of a 64-step horizon at seed 7, family 3. They DIFFER because the strategy index is
# the `dim1` coordinate of that stream and nothing else changes; both are re-derived from
# `rng_bernoulli` below rather than trusted from here.
comptime MIXED_ACTS_S0: Int = 368
comptime MIXED_ACTS_S1: Int = 373

# The stated band for the statistical-tie assertion, in standard errors of the paired mean. A
# two-sided normal tail of 0.0027; deterministic at a fixed seed.
comptime TIE_SIGMA_BAND: Float64 = 3.0

# The floor the measured variance ratio must clear. MEASURED at 174.08; gated at 100 so the gate
# is a SHAPE gate that can still fail if pairing ever stops working, rather than an exact float
# that would fail on an unrelated change to how a variance is summed.
comptime RATIO_FLOOR: Float64 = 100.0


def main():
    var passed = 0
    var failed = 0
    print("\n[strategy.crn] known-value suite")

    # ── the identifiers, delegated and not restated ────────────────────────────
    var ids_ok = crn_contract_id() == strat_crn_contract()
    ids_ok = ids_ok and crn_generator_version() == strat_rng_version()
    ids_ok = ids_ok and crn_generator_version() == String("philox4x64-10/v1")
    ids_ok = ids_ok and crn_contract_id() == String(
        "seed:key0,family:key1,scenario:counter0,step:dim0,factor:dim1,process:stream/v1"
    )
    ids_ok = ids_ok and crn_environment_id() == String(
        "value:sum_factors-cost,act:policy,payoff:sum_t gamma^t act_t value_t/v1"
    )
    if ids_ok:
        passed += 1
        print(
            "  ✅ the generator and coordinate identifiers are the contract's own, not a",
            "second spelling:", crn_contract_id(),
        )
    else:
        failed += 1
        print("  ❌ an identifier drifted from the contract:", crn_contract_id())

    # ── the named streams, derived by name and distinct ────────────────────────
    var scen_stream = crn_scenario_stream()
    var pol_stream = crn_policy_stream()
    var streams_ok = scen_stream == Int(stream_id("strategy.scenario"))
    streams_ok = streams_ok and pol_stream == Int(stream_id("strategy.policy"))
    streams_ok = streams_ok and scen_stream != pol_stream
    streams_ok = streams_ok and scen_stream >= 8 and scen_stream <= 65534
    streams_ok = streams_ok and pol_stream >= 8 and pol_stream <= 65534
    if streams_ok:
        passed += 1
        print(
            "  ✅ scenario stream", scen_stream, "and policy stream", pol_stream,
            "are derived from names, distinct, and inside [8, 65534]",
        )
    else:
        failed += 1
        print("  ❌ a stream id is hardcoded or collides:", scen_stream, pol_stream)

    # ── arity is computed from the environment ─────────────────────────────────
    var ar_ok = crn_policy_arity(STRAT_POLICY_CONSTANT, 1) == 1
    ar_ok = ar_ok and crn_policy_arity(STRAT_POLICY_THRESHOLD, 1) == 2
    ar_ok = ar_ok and crn_policy_arity(STRAT_POLICY_THRESHOLD, 4) == 5
    ar_ok = ar_ok and crn_policy_arity(STRAT_POLICY_MIXED, 1) == 2
    ar_ok = ar_ok and crn_policy_arity(STRAT_POLICY_TABULAR, 1) == -1
    ar_ok = ar_ok and crn_policy_arity(99, 1) == -1
    if ar_ok:
        passed += 1
        print(
            "  ✅ arity is a function of the environment: CONSTANT 1, THRESHOLD n_factors+1,",
            "MIXED 2 actions, TABULAR -1 in a stateless environment",
        )
    else:
        failed += 1
        print("  ❌ an arity is not the environment's:", crn_policy_arity(STRAT_POLICY_THRESHOLD, 4))

    # ── every tape cell equals the FROZEN draw at the declared coordinates ─────
    var st = UInt64(scen_stream)
    var tape = crn_scenario_tape(7, 3, 5, 4, 2, STRAT_FACTOR_UNIFORM, 0.0)
    var coords_ok = len(tape) == 8
    for t in range(4):
        for j in range(2):
            if tape[t * 2 + j] != rng_uniform(7, 3, 5, UInt64(t), UInt64(j), st, 0):
                coords_ok = False
    if coords_ok:
        passed += 1
        print(
            "  ✅ every uniform cell equals the FROZEN rng_uniform at (seed=k0, family=k1,",
            "scenario=counter0, step=dim0, factor=dim1, named stream) — bit for bit",
        )
    else:
        failed += 1
        print("  ❌ the tape coordinates are not the declared ones")

    var exp_tape = crn_scenario_tape(7, 3, 5, 3, 1, STRAT_FACTOR_EXPONENTIAL, 2.0)
    var nor_tape = crn_scenario_tape(7, 3, 5, 3, 1, STRAT_FACTOR_NORMAL, 0.0)
    var ber_tape = crn_scenario_tape(7, 3, 5, 3, 1, STRAT_FACTOR_BERNOULLI, 0.5)
    var kinds_ok = len(exp_tape) == 3 and len(nor_tape) == 3 and len(ber_tape) == 3
    for t in range(3):
        var tt = UInt64(t)
        if exp_tape[t] != rng_exponential(7, 3, 5, tt, 0, st, 0, 2.0):
            kinds_ok = False
        if nor_tape[t] != rng_normal(7, 3, 5, tt, 0, st, 0):
            kinds_ok = False
        var expect_b: Float64 = 0.0
        if rng_bernoulli(7, 3, 5, tt, 0, st, 0, 0.5):
            expect_b = 1.0
        if ber_tape[t] != expect_b:
            kinds_ok = False
    if kinds_ok:
        passed += 1
        print(
            "  ✅ exponential, standard-normal and Bernoulli cells each equal the frozen",
            "distribution kernel at the same coordinates",
        )
    else:
        failed += 1
        print("  ❌ a factor distribution is not the frozen one")

    # ── the golden digest ─────────────────────────────────────────────────────
    var d5 = crn_scenario_digest(7, 3, 5, 4, 2, STRAT_FACTOR_UNIFORM, 0.0)
    var d6 = crn_scenario_digest(7, 3, 6, 4, 2, STRAT_FACTOR_UNIFORM, 0.0)
    if d5 == GOLDEN_DIGEST_S5 and d6 == GOLDEN_DIGEST_S6 and d5 != d6:
        passed += 1
        print("  ✅ golden bit-exact digests hold: scenario 5 =", d5, "scenario 6 =", d6)
    else:
        failed += 1
        print("  ❌ a golden digest changed — the generator or the assignment moved:", d5, d6)

    # ── ASSERTION 1: two evaluations at one seed see BIT-IDENTICAL raw draws ───
    var tape_a = crn_scenario_tape(7, 3, 5, 4, 2, STRAT_FACTOR_UNIFORM, 0.0)
    var tape_b = crn_scenario_tape(7, 3, 5, 4, 2, STRAT_FACTOR_UNIFORM, 0.0)
    var raw_ok = len(tape_a) == 8 and len(tape_b) == 8
    for c in range(8):
        if tape_a[c] != tape_b[c]:
            raw_ok = False
    raw_ok = raw_ok and crn_scenario_digest(7, 3, 5, 4, 2, STRAT_FACTOR_UNIFORM, 0.0) == d5
    if raw_ok:
        passed += 1
        print(
            "  ✅ two independent generations at one (seed, family, scenario) agree on every RAW",
            "DRAW — the generation call has no strategy argument, so it cannot differ",
        )
    else:
        failed += 1
        print("  ❌ two generations at identical coordinates disagreed")

    # Two DIFFERENT policies, evaluated on the same tape, report the same tape digest.
    # Two THRESHOLD rows over TWO factors, so arity is 3 (two weights, then the threshold) and
    # the block is 2 x 3. The two rows differ only in the threshold, so they decide differently
    # and still read the identical scenario.
    var pol_a = List[Float64]()
    pol_a.append(1.0)
    pol_a.append(1.0)
    pol_a.append(0.80)
    pol_a.append(1.0)
    pol_a.append(1.0)
    pol_a.append(1.20)
    var out_a = crn_evaluate_on_tape(
        tape_a, 4, 2, STRAT_POLICY_THRESHOLD, pol_a, 2, 3, 0, 0.5, 1.0, 7, 3, 5
    )
    var out_b = crn_evaluate_on_tape(
        tape_a, 4, 2, STRAT_POLICY_THRESHOLD, pol_a, 2, 3, 1, 0.5, 1.0, 7, 3, 5
    )
    var same_scene = out_a.status == STRAT_OK and out_b.status == STRAT_OK
    same_scene = same_scene and out_a.has_digest and out_b.has_digest
    same_scene = same_scene and out_a.digest == out_b.digest and out_a.digest == d5
    same_scene = same_scene and out_a.strategy == 0 and out_b.strategy == 1
    # And they really did decide differently — otherwise "same scenario" would be vacuous.
    same_scene = same_scene and out_a.n_acted != out_b.n_acted
    if same_scene:
        passed += 1
        print(
            "  ✅ two different threshold policies on one tape report the identical scenario",
            "digest", out_a.digest, "— pairing is a property of the address, not of the caller",
        )
    else:
        failed += 1
        print("  ❌ two policies on one tape reported different scenarios")

    # ── hand-derived payoffs ──────────────────────────────────────────────────
    # theta = 0.0 always acts, cost 0, gamma 1, one factor, horizon 1: the payoff IS the draw.
    var flat = List[Float64]()
    flat.append(1.0)
    flat.append(0.0)
    var one = crn_evaluate_policy(
        7, 3, 4, 1, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.0, STRAT_POLICY_THRESHOLD, flat, 2, 1.0
    )
    var one_ok = one.status == STRAT_OK and one.n_acted == 4 and one.n_tapes_built == 4
    for r in range(4):
        if one.payoffs[r] != rng_uniform(7, 3, UInt64(r), 0, 0, st, 0):
            one_ok = False
        if not one.payoff_present[r]:
            one_ok = False
    if one_ok:
        passed += 1
        print(
            "  ✅ at horizon 1, cost 0, gamma 1 and an always-act threshold, the payoff IS the",
            "frozen draw, exactly, on all four scenarios",
        )
    else:
        failed += 1
        print("  ❌ the horizon-1 payoff is not the draw:", one.payoffs[0])

    # gamma = 0.5 over three steps: x0 + 0.5 x1 + 0.25 x2, accumulated in the same order.
    var three = crn_evaluate_policy(
        7, 3, 4, 3, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.0, STRAT_POLICY_THRESHOLD, flat, 2, 0.5
    )
    var disc_ok = three.status == STRAT_OK and three.n_acted == 12
    for r in range(4):
        var rr = UInt64(r)
        var x0 = rng_uniform(7, 3, rr, 0, 0, st, 0)
        var x1 = rng_uniform(7, 3, rr, 1, 0, st, 0)
        var x2 = rng_uniform(7, 3, rr, 2, 0, st, 0)
        if three.payoffs[r] != x0 + 0.5 * x1 + 0.25 * x2:
            disc_ok = False
    if disc_ok:
        passed += 1
        print(
            "  ✅ the discounted payoff is exactly x0 + 0.5*x1 + 0.25*x2 from the frozen draws,",
            "to the last bit, on all four scenarios",
        )
    else:
        failed += 1
        print("  ❌ the discounted sum is not gamma^t weighted:", three.payoffs[0])

    # gamma = 0.0 is myopic: only step 0 contributes.
    var myopic = crn_evaluate_policy(
        7, 3, 4, 3, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.0, STRAT_POLICY_THRESHOLD, flat, 2, 0.0
    )
    var myopic_ok = myopic.status == STRAT_OK
    for r in range(4):
        if myopic.payoffs[r] != rng_uniform(7, 3, UInt64(r), 0, 0, st, 0):
            myopic_ok = False
    if myopic_ok:
        passed += 1
        print("  ✅ gamma = 0.0 is a legal, myopic request: only step 0 enters the payoff")
    else:
        failed += 1
        print("  ❌ gamma = 0.0 was mishandled:", myopic.status, myopic.payoffs[0])

    # ── absence is not zero ───────────────────────────────────────────────────
    var hold = List[Float64]()
    hold.append(0.0)
    var held = crn_evaluate_policy(
        7, 3, 4, 3, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.5, STRAT_POLICY_CONSTANT, hold, 1, 1.0
    )
    var hold_ok = held.status == STRAT_OK and held.n_acted == 0 and held.n_absent == 0
    hold_ok = hold_ok and held.has_mean and held.mean == 0.0
    for r in range(4):
        hold_ok = hold_ok and held.payoffs[r] == 0.0 and held.payoff_present[r]
    if hold_ok:
        passed += 1
        print(
            "  ✅ a policy that never acts has a payoff of exactly 0.0 with payoff_present TRUE",
            "— a real zero, distinct from an absent payoff",
        )
    else:
        failed += 1
        print("  ❌ a never-acting policy was reported as absent:", held.payoff_present[0])

    var always = List[Float64]()
    always.append(1.0)
    var acts = crn_evaluate_policy(
        7, 3, 4, 3, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.5, STRAT_POLICY_CONSTANT, always, 1, 1.0
    )
    var act_ok = acts.status == STRAT_OK and acts.n_acted == 12
    for r in range(4):
        var rr2 = UInt64(r)
        var s0 = rng_uniform(7, 3, rr2, 0, 0, st, 0) - 0.5
        var s1 = rng_uniform(7, 3, rr2, 1, 0, st, 0) - 0.5
        var s2 = rng_uniform(7, 3, rr2, 2, 0, st, 0) - 0.5
        if acts.payoffs[r] != s0 + s1 + s2:
            act_ok = False
    if act_ok:
        passed += 1
        print(
            "  ✅ an always-act constant policy pays exactly sum_t (x_t - cost) from the frozen",
            "draws, and acts on all 12 steps",
        )
    else:
        failed += 1
        print("  ❌ the always-act payoff is wrong:", acts.payoffs[0])

    # ── the strategy index enters ONLY on the policy stream ───────────────────
    var mixed = List[Float64]()
    mixed.append(0.3)
    mixed.append(0.7)
    mixed.append(0.3)
    mixed.append(0.7)
    var mrun = crn_evaluate_policies(
        7, 3, 8, 64, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.5, STRAT_POLICY_MIXED, mixed, 2, 2, 1.0
    )
    var ps = UInt64(pol_stream)
    var hand0 = 0
    var hand1 = 0
    for r in range(8):
        for t in range(64):
            if rng_bernoulli(7, 3, UInt64(r), UInt64(t), 0, ps, 0, 0.7):
                hand0 += 1
            if rng_bernoulli(7, 3, UInt64(r), UInt64(t), 1, ps, 0, 0.7):
                hand1 += 1
    var mix_ok = mrun.status == STRAT_OK and mrun.n_tapes_built == 8
    mix_ok = mix_ok and mrun.n_acted[0] == hand0 and mrun.n_acted[1] == hand1
    mix_ok = mix_ok and hand0 == MIXED_ACTS_S0 and hand1 == MIXED_ACTS_S1
    mix_ok = mix_ok and mrun.n_acted[0] != mrun.n_acted[1]
    if mix_ok:
        passed += 1
        print(
            "  ✅ two IDENTICAL mixed rows share every scenario (8 tapes for 8 scenarios) but",
            "draw different coins —", mrun.n_acted[0], "vs", mrun.n_acted[1],
            "acts, each equal to the frozen rng_bernoulli at (step=dim0, strategy=dim1)",
        )
    else:
        failed += 1
        print(
            "  ❌ the policy stream is not addressed by (step, strategy):", mrun.n_acted[0],
            hand0, mrun.n_acted[1], hand1,
        )

    # ── ASSERTION 2: THE VARIANCE REDUCTION, both numbers printed ─────────────
    var head = List[Float64]()
    head.append(1.0)
    head.append(0.40)
    head.append(1.0)
    head.append(0.50)
    var au = crn_pairing_audit(
        12345, 7, 32, 64, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.5, STRAT_POLICY_THRESHOLD,
        head, 2, 2, 0, 1, 1.0, 0.95,
    )
    print(
        "  ── the measurement that justifies the package ──────────────────────────────────"
    )
    print(
        "     PAIRED   mean", au.paired_mean, " variance", au.paired_variance,
        " 95% CI [", au.paired_ci_lower, ",", au.paired_ci_upper, "] p", au.paired_p_value,
    )
    print(
        "     UNPAIRED mean", au.unpaired_mean, " variance", au.unpaired_variance,
        " 95% CI [", au.unpaired_ci_lower, ",", au.unpaired_ci_upper, "] p", au.unpaired_p_value,
    )
    print(
        "     variance ratio unpaired/paired =", au.variance_ratio,
        " paired variance strictly lower:", au.pairing_reduces_variance,
    )
    var head_ok = au.status == STRAT_OK and au.n_scenarios_used == 32
    head_ok = head_ok and au.n_scenarios_bit_identical == 32 and au.n_tapes_built == 96
    head_ok = head_ok and au.has_paired and au.has_unpaired
    head_ok = head_ok and au.paired_variance < au.unpaired_variance
    head_ok = head_ok and au.pairing_reduces_variance
    head_ok = head_ok and au.has_variance_ratio and au.variance_ratio > RATIO_FLOOR
    head_ok = head_ok and au.scenario_sets_differ
    if head_ok:
        passed += 1
        print(
            "  ✅ the paired comparison has STRICTLY lower variance —", au.paired_variance,
            "against", au.unpaired_variance, "— a factor of", au.variance_ratio,
            "at identical work, with all 32 scenarios verified bit-identical across the two",
            "strategies",
        )
    else:
        failed += 1
        print(
            "  ❌ pairing did NOT reduce variance, or a scenario was not bit-identical:",
            au.status, au.paired_variance, au.unpaired_variance, au.n_scenarios_bit_identical,
        )

    var conclude_ok = au.has_paired_ci and au.has_unpaired_ci
    conclude_ok = conclude_ok and au.paired_excludes_zero and not au.unpaired_excludes_zero
    conclude_ok = conclude_ok and au.conclusions_differ
    conclude_ok = conclude_ok and au.has_paired_p and au.paired_p_value < 1.0e-10
    conclude_ok = conclude_ok and au.has_unpaired_p and au.unpaired_p_value > 0.05
    if conclude_ok:
        passed += 1
        print(
            "  ✅ and the two conclusions DIFFER: the paired interval excludes zero (p",
            au.paired_p_value, ") while the unpaired one contains it (p", au.unpaired_p_value,
            ") — the unpaired comparison cannot rank policies the paired one separates",
        )
    else:
        failed += 1
        print(
            "  ❌ the conclusions did not diverge as measured:", au.paired_excludes_zero,
            au.unpaired_excludes_zero, au.conclusions_differ,
        )

    # ── "no difference" is a VALUE: the exact tie, twice over ─────────────────
    var repar = List[Float64]()
    repar.append(1.0)
    repar.append(0.40)
    repar.append(2.0)
    repar.append(0.80)
    var tie1 = crn_pairing_audit(
        12345, 7, 32, 64, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.5, STRAT_POLICY_THRESHOLD,
        repar, 2, 2, 0, 1, 1.0, 0.95,
    )
    var dup = List[Float64]()
    dup.append(1.0)
    dup.append(0.40)
    dup.append(1.0)
    dup.append(0.40)
    var tie2 = crn_pairing_audit(
        12345, 7, 32, 64, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.5, STRAT_POLICY_THRESHOLD,
        dup, 2, 2, 0, 1, 1.0, 0.95,
    )
    var tie_ok = tie1.status == STRAT_OK and tie2.status == STRAT_OK
    tie_ok = tie_ok and tie1.paired_mean == 0.0 and tie1.paired_variance == 0.0
    tie_ok = tie_ok and tie2.paired_mean == 0.0 and tie2.paired_variance == 0.0
    tie_ok = tie_ok and tie1.has_paired_p and tie1.paired_p_value == 1.0
    tie_ok = tie_ok and tie2.has_paired_p and tie2.paired_p_value == 1.0
    tie_ok = tie_ok and not tie1.paired_excludes_zero and not tie2.paired_excludes_zero
    tie_ok = tie_ok and not tie1.has_variance_ratio and not tie2.has_variance_ratio
    tie_ok = tie_ok and tie1.unpaired_variance > 0.0 and tie2.unpaired_variance > 0.0
    tie_ok = tie_ok and tie1.unpaired_variance == tie2.unpaired_variance
    if tie_ok:
        passed += 1
        print(
            "  ✅ the indistinguishable case is a VALUE: theta 0.40 vs the reparameterised",
            "(w=2, theta=0.8) — and vs an identical duplicate row — give a paired difference of",
            "EXACTLY 0.0 at every scenario, p = 1.0, and NO variance ratio, because an infinite",
            "ratio is not a number (the flag is the answer)",
        )
    else:
        failed += 1
        print(
            "  ❌ an exact tie was not reported as no difference:", tie1.paired_mean,
            tie1.paired_variance, tie1.paired_p_value, tie1.has_variance_ratio,
        )

    # ── the STATISTICAL tie: equal exact expectations, an estimator with noise ─
    var stie = List[Float64]()
    stie.append(1.0)
    stie.append(0.40)
    stie.append(1.0)
    stie.append(0.60)
    var t200 = crn_pairing_audit(
        12345, 7, 200, 64, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.5, STRAT_POLICY_THRESHOLD,
        stie, 2, 2, 0, 1, 1.0, 0.95,
    )
    var t500 = crn_pairing_audit(
        12345, 7, 500, 64, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.5, STRAT_POLICY_THRESHOLD,
        stie, 2, 2, 0, 1, 1.0, 0.95,
    )
    var z200 = t200.paired_mean / sqrt(t200.paired_variance / Float64(t200.n_scenarios_used))
    var z500 = t500.paired_mean / sqrt(t500.paired_variance / Float64(t500.n_scenarios_used))
    print(
        "     statistical tie (0.40 vs 0.60, equal exact expectation 0.12/step): n=200 mean",
        t200.paired_mean, "|t|", z200, "p", t200.paired_p_value, "CI excludes 0:",
        t200.paired_excludes_zero,
    )
    print(
        "                                                                       n=500 mean",
        t500.paired_mean, "|t|", z500, "p", t500.paired_p_value, "CI excludes 0:",
        t500.paired_excludes_zero,
    )
    var stie_ok = t200.status == STRAT_OK and t500.status == STRAT_OK
    stie_ok = stie_ok and z200 < TIE_SIGMA_BAND and z200 > -TIE_SIGMA_BAND
    stie_ok = stie_ok and z500 < TIE_SIGMA_BAND and z500 > -TIE_SIGMA_BAND
    stie_ok = stie_ok and t200.paired_variance < t200.unpaired_variance
    stie_ok = stie_ok and t500.paired_variance < t500.unpaired_variance
    stie_ok = stie_ok and not t500.paired_excludes_zero
    if stie_ok:
        passed += 1
        print(
            "  ✅ two exactly-tied thresholds sit inside a 3-sigma band of zero at both sample",
            "sizes. NOT BURIED: at n=200 the 95% interval EXCLUDES zero for a true tie — the",
            "5%-level false positive, which is why a ranking must carry its interval and not",
            "just a winner",
        )
    else:
        failed += 1
        print("  ❌ a tied pair drifted outside its own 3-sigma band:", z200, z500)

    # ── independence across scenarios, over DISJOINT pairs ────────────────────
    var i1 = crn_independence_audit(999, 3, 512, 64, 2, STRAT_FACTOR_UNIFORM, 0.0, 1)
    var i2 = crn_independence_audit(999, 3, 512, 64, 2, STRAT_FACTOR_UNIFORM, 0.0, 2)
    var i3 = crn_independence_audit(999, 3, 512, 64, 2, STRAT_FACTOR_NORMAL, 0.0, 1)
    print(
        "     independence: lag 1", i1.n_scenario_pairs, "pairs /", i1.n_draw_pairs,
        "draw pairs  r", i1.correlation, " z", i1.z_score, " p", i1.p_value,
    )
    print(
        "                   lag 2", i2.n_scenario_pairs, "pairs /", i2.n_draw_pairs,
        "draw pairs  r", i2.correlation, " z", i2.z_score,
    )
    print(
        "                   lag 1, standard-normal factors  r", i3.correlation,
        " z", i3.z_score,
    )
    var ind_ok = i1.status == STRAT_OK and i2.status == STRAT_OK and i3.status == STRAT_OK
    # Hand-derived: stride lag+1, pair i uses i*(lag+1) and i*(lag+1)+lag.
    ind_ok = ind_ok and i1.n_scenario_pairs == 256 and i1.n_draw_pairs == 256 * 128
    ind_ok = ind_ok and i2.n_scenario_pairs == 170 and i2.n_draw_pairs == 170 * 128
    ind_ok = ind_ok and i1.has_correlation and i2.has_correlation and i3.has_correlation
    ind_ok = ind_ok and i1.indistinguishable_from_zero
    ind_ok = ind_ok and i2.indistinguishable_from_zero
    ind_ok = ind_ok and i3.indistinguishable_from_zero
    ind_ok = ind_ok and i1.has_noise_scale and i1.noise_scale > 0.0
    ind_ok = ind_ok and i1.has_p_value and i1.p_value > 0.01
    if ind_ok:
        passed += 1
        print(
            "  ✅ scenario i and scenario i+lag are uncorrelated at lags 1 and 2 and under two",
            "distributions: |z| =", i1.z_score, i2.z_score, i3.z_score,
            "against a band of", i1.z_band, "— measured over disjoint pairs, not asserted",
        )
    else:
        failed += 1
        print(
            "  ❌ consecutive scenarios are correlated or the pair count is wrong:",
            i1.n_scenario_pairs, i1.z_score, i2.n_scenario_pairs, i2.z_score,
        )

    # ── the work charge can REFUSE ────────────────────────────────────────────
    var cheap = crn_request_status(
        2, 2048, 2048, 1, STRAT_FACTOR_UNIFORM, 0.0, STRAT_POLICY_THRESHOLD, 2, 0.0, 1.0
    )
    var costly = crn_pairing_audit(
        1, 1, 2048, 2048, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.0, STRAT_POLICY_THRESHOLD,
        head, 2, 2, 0, 1, 1.0, 0.95,
    )
    var over = crn_request_status(
        64, 512, 4096, 8, STRAT_FACTOR_UNIFORM, 0.0, STRAT_POLICY_THRESHOLD, 9, 0.0, 1.0
    )
    var budget_ok = cheap == STRAT_OK and costly.status == STRAT_ERR_WORK_BUDGET
    budget_ok = budget_ok and costly.work_charged == -1 and over == STRAT_ERR_WORK_BUDGET
    budget_ok = budget_ok and au.work_charged == 413696
    if budget_ok:
        passed += 1
        print(
            "  ✅ the charge can FAIL: a 2-policy comparison over 2048x2048 is accepted while",
            "the 3-tape audit of the same shape is refused work_budget_exceeded, and the",
            "32-scenario audit above charged", au.work_charged, "units",
        )
    else:
        failed += 1
        print("  ❌ the work charge accepted or refused the wrong shape:", cheap, costly.status, over)

    # ── refusals: the aliasing case, every range, every kind ──────────────────
    var bleed = crn_cell_draw(1, 1, 1, 0, 65536, 65537, STRAT_FACTOR_UNIFORM, 0.0)
    var ceil = crn_cell_draw(1, 1, 1, 0, 256, 257, STRAT_FACTOR_UNIFORM, 0.0)
    var alias_ok = bleed.status == STRAT_ERR_FACTOR_RANGE and not bleed.has_value
    alias_ok = alias_ok and bleed.value == 0.0 and bleed.cell == -1
    alias_ok = alias_ok and ceil.status == STRAT_ERR_FACTOR_RANGE
    if alias_ok:
        passed += 1
        print(
            "  ✅ factor 65536 is REFUSED: it would set bit 32 of (step<<32)|(factor<<16)|stream",
            "and make cell (0, 65536) return the identical draw to cell (1, 0)",
        )
    else:
        failed += 1
        print("  ❌ the aliasing coordinate was accepted:", bleed.status, bleed.value)

    var good = crn_cell_draw(7, 3, 5, 1, 1, 2, STRAT_FACTOR_UNIFORM, 0.0)
    var cell_ok = good.status == STRAT_OK and good.has_value and good.cell == 3
    cell_ok = cell_ok and good.stream == scen_stream and good.draws_per_cell == 1
    cell_ok = cell_ok and good.value == rng_uniform(7, 3, 5, 1, 1, st, 0)
    cell_ok = cell_ok and good.value == tape[3]
    var nrm = crn_cell_draw(7, 3, 5, 0, 0, 1, STRAT_FACTOR_NORMAL, 0.0)
    cell_ok = cell_ok and nrm.status == STRAT_OK and nrm.draws_per_cell == 2
    if cell_ok:
        passed += 1
        print(
            "  ✅ a single addressed cell equals the frozen draw AND the tape entry at the same",
            "row-major offset; the normal declares 2 draws per cell (Box-Muller)",
        )
    else:
        failed += 1
        print("  ❌ a single cell disagrees with the tape:", good.value, tape[3], nrm.draws_per_cell)

    var coord_refusals = crn_cell_draw(-1, 1, 1, 0, 0, 1, STRAT_FACTOR_UNIFORM, 0.0).status
    var cr_ok = coord_refusals == STRAT_ERR_SEED_RANGE
    cr_ok = cr_ok and crn_cell_draw(
        1, -1, 1, 0, 0, 1, STRAT_FACTOR_UNIFORM, 0.0
    ).status == STRAT_ERR_SEED_RANGE
    cr_ok = cr_ok and crn_cell_draw(
        1, 1, -1, 0, 0, 1, STRAT_FACTOR_UNIFORM, 0.0
    ).status == STRAT_ERR_SEED_RANGE
    cr_ok = cr_ok and crn_cell_draw(
        1, 1, 4096, 0, 0, 1, STRAT_FACTOR_UNIFORM, 0.0
    ).status == STRAT_ERR_SCENARIO_RANGE
    cr_ok = cr_ok and crn_cell_draw(
        1, 1, 1, 65536, 0, 1, STRAT_FACTOR_UNIFORM, 0.0
    ).status == STRAT_ERR_HORIZON_RANGE
    cr_ok = cr_ok and crn_cell_draw(
        1, 1, 1, 0, 3, 2, STRAT_FACTOR_UNIFORM, 0.0
    ).status == STRAT_ERR_SHAPE
    if cr_ok:
        passed += 1
        print(
            "  ✅ six coordinate refusals, each with its own code: negative seed, family and",
            "scenario (they wrap to enormous UInt64 coordinates), scenario past the ceiling,",
            "step past the horizon ceiling, factor past the tape's own width",
        )
    else:
        failed += 1
        print("  ❌ a coordinate refusal used the wrong code:", coord_refusals)

    var nan = 0.0 / 0.0
    var req_ok = crn_request_status(
        1, 4, 3, 1, STRAT_FACTOR_UNIFORM, 0.0, STRAT_POLICY_TABULAR, 1, 0.0, 1.0
    ) == STRAT_ERR_NOT_EVALUABLE
    req_ok = req_ok and crn_request_status(
        1, 4, 3, 1, STRAT_FACTOR_UNIFORM, 0.0, 99, 1, 0.0, 1.0
    ) == STRAT_ERR_POLICY_KIND
    req_ok = req_ok and crn_request_status(
        1, 4, 3, 1, STRAT_FACTOR_UNIFORM, 0.0, STRAT_POLICY_THRESHOLD, 5, 0.0, 1.0
    ) == STRAT_ERR_POLICY_ARITY
    req_ok = req_ok and crn_request_status(
        1, 4, 3, 1, 99, 0.0, STRAT_POLICY_THRESHOLD, 2, 0.0, 1.0
    ) == STRAT_ERR_NOT_EVALUABLE
    req_ok = req_ok and crn_request_status(
        1, 4, 3, 1, STRAT_FACTOR_EXPONENTIAL, 0.0, STRAT_POLICY_THRESHOLD, 2, 0.0, 1.0
    ) == STRAT_ERR_NOT_EVALUABLE
    req_ok = req_ok and crn_request_status(
        1, 4, 3, 1, STRAT_FACTOR_EXPONENTIAL, -1.0, STRAT_POLICY_THRESHOLD, 2, 0.0, 1.0
    ) == STRAT_ERR_NOT_EVALUABLE
    req_ok = req_ok and crn_request_status(
        1, 4, 3, 1, STRAT_FACTOR_BERNOULLI, 1.5, STRAT_POLICY_THRESHOLD, 2, 0.0, 1.0
    ) == STRAT_ERR_PROBABILITY
    req_ok = req_ok and crn_request_status(
        1, 4, 3, 1, STRAT_FACTOR_BERNOULLI, -0.1, STRAT_POLICY_THRESHOLD, 2, 0.0, 1.0
    ) == STRAT_ERR_PROBABILITY
    req_ok = req_ok and crn_request_status(
        1, 4, 3, 1, STRAT_FACTOR_UNIFORM, nan, STRAT_POLICY_THRESHOLD, 2, 0.0, 1.0
    ) == STRAT_ERR_NON_FINITE
    req_ok = req_ok and crn_request_status(
        1, 4, 3, 1, STRAT_FACTOR_UNIFORM, 0.0, STRAT_POLICY_THRESHOLD, 2, nan, 1.0
    ) == STRAT_ERR_NON_FINITE
    req_ok = req_ok and crn_request_status(
        1, 4, 3, 1, STRAT_FACTOR_UNIFORM, 0.0, STRAT_POLICY_THRESHOLD, 2, 0.0, 1.5
    ) == STRAT_ERR_DISCOUNT_RANGE
    req_ok = req_ok and crn_request_status(
        1, 4, 3, 1, STRAT_FACTOR_UNIFORM, 0.0, STRAT_POLICY_THRESHOLD, 2, 0.0, nan
    ) == STRAT_ERR_DISCOUNT_RANGE
    req_ok = req_ok and crn_request_status(
        1, 1, 3, 1, STRAT_FACTOR_UNIFORM, 0.0, STRAT_POLICY_THRESHOLD, 2, 0.0, 1.0
    ) == STRAT_ERR_TOO_FEW_REPLICATIONS
    req_ok = req_ok and crn_request_status(
        1, 4, 0, 1, STRAT_FACTOR_UNIFORM, 0.0, STRAT_POLICY_THRESHOLD, 2, 0.0, 1.0
    ) == STRAT_ERR_HORIZON_RANGE
    req_ok = req_ok and crn_request_status(
        1, 4, 3, 0, STRAT_FACTOR_UNIFORM, 0.0, STRAT_POLICY_THRESHOLD, 1, 0.0, 1.0
    ) == STRAT_ERR_FACTOR_RANGE
    req_ok = req_ok and crn_request_status(
        1, 4, 3, 257, STRAT_FACTOR_UNIFORM, 0.0, STRAT_POLICY_THRESHOLD, 258, 0.0, 1.0
    ) == STRAT_ERR_FACTOR_RANGE
    if req_ok:
        passed += 1
        print(
            "  ✅ sixteen request refusals, each naming its own defect: TABULAR in a stateless",
            "environment, an unknown kind, a mismatched arity, an unknown distribution, a",
            "non-positive exponential rate, a Bernoulli p outside [0,1], a NaN parameter, a NaN",
            "cost, a discount above 1 and a NaN one, one scenario, a zero horizon, and a factor",
            "count of 0 and of 257",
        )
    else:
        failed += 1
        print("  ❌ a request refusal used the wrong code")

    # ── the tape refuses by returning EMPTY, never by aborting ────────────────
    var empties = len(crn_scenario_tape(-1, 0, 0, 3, 1, STRAT_FACTOR_UNIFORM, 0.0)) == 0
    empties = empties and len(crn_scenario_tape(1, -1, 0, 3, 1, STRAT_FACTOR_UNIFORM, 0.0)) == 0
    empties = empties and len(crn_scenario_tape(1, 0, -1, 3, 1, STRAT_FACTOR_UNIFORM, 0.0)) == 0
    empties = empties and len(crn_scenario_tape(1, 0, 0, 0, 1, STRAT_FACTOR_UNIFORM, 0.0)) == 0
    empties = empties and len(crn_scenario_tape(1, 0, 0, 3, 0, STRAT_FACTOR_UNIFORM, 0.0)) == 0
    empties = empties and len(crn_scenario_tape(1, 0, 0, 3, 257, STRAT_FACTOR_UNIFORM, 0.0)) == 0
    empties = empties and len(crn_scenario_tape(1, 0, 4096, 3, 1, STRAT_FACTOR_UNIFORM, 0.0)) == 0
    empties = empties and len(crn_scenario_tape(1, 0, 0, 3, 1, 99, 0.0)) == 0
    empties = empties and len(crn_scenario_tape(1, 0, 0, 3, 1, STRAT_FACTOR_UNIFORM, nan)) == 0
    empties = empties and crn_scenario_digest(1, 0, 0, 0, 1, STRAT_FACTOR_UNIFORM, 0.0) == -1
    if empties:
        passed += 1
        print(
            "  ✅ nine tape refusals return an EMPTY list and the digest returns -1: a valid",
            "call always returns exactly horizon * n_factors cells, so the two cannot be confused",
        )
    else:
        failed += 1
        print("  ❌ a refused tape returned cells")

    # ── THE COUNT TRAPS: a count past the list must not abort the worker ──────
    var tiny = List[Float64]()
    tiny.append(1.0)
    tiny.append(2.0)
    tiny.append(3.0)
    var trap_ok = crn_evaluate_on_tape(
        tiny, 3, 1, STRAT_POLICY_CONSTANT, tiny, 5, 1, 0, 0.0, 1.0, 1, 1, 1
    ).status == STRAT_ERR_SHAPE
    trap_ok = trap_ok and crn_evaluate_on_tape(
        tiny, 99, 1, STRAT_POLICY_CONSTANT, tiny, 3, 1, 0, 0.0, 1.0, 1, 1, 1
    ).status == STRAT_ERR_SHAPE
    trap_ok = trap_ok and crn_evaluate_on_tape(
        tiny, 3, 1, STRAT_POLICY_CONSTANT, tiny, 3, 1, 7, 0.0, 1.0, 1, 1, 1
    ).status == STRAT_ERR_TOO_FEW_STRATEGIES
    trap_ok = trap_ok and crn_evaluate_on_tape(
        tiny, 3, 1, STRAT_POLICY_CONSTANT, tiny, 3, 1, -1, 0.0, 1.0, 1, 1, 1
    ).status == STRAT_ERR_TOO_FEW_STRATEGIES
    trap_ok = trap_ok and crn_evaluate_policies(
        1, 1, 4, 3, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.0, STRAT_POLICY_CONSTANT, tiny, 9, 1, 1.0
    ).status == STRAT_ERR_SHAPE
    trap_ok = trap_ok and crn_evaluate_policies(
        1, 1, 4, 3, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.0, STRAT_POLICY_CONSTANT, tiny, 3, 2, 1.0
    ).status == STRAT_ERR_POLICY_ARITY
    if trap_ok:
        passed += 1
        print(
            "  ✅ every count-versus-length trap is a typed status and not an abort:",
            "n_strategies 5 against 3 parameters, horizon 99 against a 3-cell tape,",
            "strategy 7 of 3, strategy -1, n_strategies 9 against 3, and a mismatched arity",
        )
    else:
        failed += 1
        print("  ❌ a count trap returned the wrong code")

    # ── policy-row refusals ──────────────────────────────────────────────────
    var bad_const = List[Float64]()
    bad_const.append(0.7)
    var row_ok = crn_evaluate_policy(
        1, 1, 4, 3, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.0, STRAT_POLICY_CONSTANT, bad_const, 1, 1.0
    ).status == STRAT_ERR_ACTION_RANGE
    var bad_mix = List[Float64]()
    bad_mix.append(0.3)
    bad_mix.append(0.5)
    row_ok = row_ok and crn_evaluate_policy(
        1, 1, 4, 3, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.0, STRAT_POLICY_MIXED, bad_mix, 2, 1.0
    ).status == STRAT_ERR_PROBABILITY
    var wide = List[Float64]()
    for _ in range(257):
        wide.append(0.5)
        wide.append(0.5)
    row_ok = row_ok and crn_evaluate_policies(
        1, 1, 2, 1, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.0, STRAT_POLICY_MIXED, wide, 257, 2, 1.0
    ).status == STRAT_ERR_DIMENSION_TOO_LARGE
    if row_ok:
        passed += 1
        print(
            "  ✅ a constant action of 0.7 is refused rather than rounded, a mixed row summing",
            "to 0.8 is refused as not a distribution, and 257 mixed strategies is refused",
            "because the strategy index is a 256-wide dim1 coordinate on the policy stream",
        )
    else:
        failed += 1
        print("  ❌ a malformed policy row was accepted")

    # ── audit and independence refusals ──────────────────────────────────────
    var au_ok = crn_pairing_audit(
        1, 1, 8, 4, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.0, STRAT_POLICY_THRESHOLD,
        head, 2, 2, 1, 1, 1.0, 0.95,
    ).status == STRAT_ERR_TOO_FEW_STRATEGIES
    au_ok = au_ok and crn_pairing_audit(
        1, 1, 8, 4, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.0, STRAT_POLICY_THRESHOLD,
        head, 2, 2, 0, 9, 1.0, 0.95,
    ).status == STRAT_ERR_TOO_FEW_STRATEGIES
    au_ok = au_ok and crn_pairing_audit(
        1, 1, 8, 4, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.0, STRAT_POLICY_THRESHOLD,
        head, 2, 2, 0, 1, 1.0, 0.0,
    ).status == STRAT_ERR_LEVEL_RANGE
    au_ok = au_ok and crn_pairing_audit(
        1, 1, 8, 4, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.0, STRAT_POLICY_THRESHOLD,
        head, 2, 2, 0, 1, 1.0, 1.0,
    ).status == STRAT_ERR_LEVEL_RANGE
    au_ok = au_ok and crn_pairing_audit(
        1, 1, 8, 4, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.0, STRAT_POLICY_THRESHOLD,
        head, 2, 2, 0, 1, 1.0, nan,
    ).status == STRAT_ERR_LEVEL_RANGE
    au_ok = au_ok and crn_pairing_audit(
        1, 1, 2049, 4, 1, STRAT_FACTOR_UNIFORM, 0.0, 0.0, STRAT_POLICY_THRESHOLD,
        head, 2, 2, 0, 1, 1.0, 0.95,
    ).status == STRAT_ERR_SCENARIO_RANGE
    au_ok = au_ok and crn_independence_audit(
        1, 1, 8, 4, 1, STRAT_FACTOR_UNIFORM, 0.0, 0
    ).status == STRAT_ERR_SCENARIO_RANGE
    au_ok = au_ok and crn_independence_audit(
        1, 1, 8, 4, 1, STRAT_FACTOR_UNIFORM, 0.0, -1
    ).status == STRAT_ERR_SCENARIO_RANGE
    au_ok = au_ok and crn_independence_audit(
        1, 1, 2, 4, 1, STRAT_FACTOR_UNIFORM, 0.0, 1
    ).status == STRAT_ERR_TOO_FEW_REPLICATIONS
    au_ok = au_ok and crn_independence_audit(
        1, 1, 8, 4, 1, 99, 0.0, 1
    ).status == STRAT_ERR_NOT_EVALUABLE
    if au_ok:
        passed += 1
        print(
            "  ✅ ten audit refusals: a strategy against itself, an out-of-range strategy, a",
            "confidence level of 0, of 1 and NaN, 2049 scenarios (the unpaired arm needs 2n",
            "addressable scenarios), lag 0 and lag -1, two scenarios, and an unknown distribution",
        )
    else:
        failed += 1
        print("  ❌ an audit refusal used the wrong code")

    print(
        "  ✅ the suite reached its own summary line, so NONE of the refused inputs above",
        "aborted the worker process",
    )
    passed += 1
    print("  [strategy.crn] Passed:", passed, "Failed:", failed)
