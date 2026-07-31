# Frozen specifications — Gate 0

**Status: FROZEN.** These are the contracts every kernel is written against. Changing any of them is
not a refactor: it invalidates golden hashes, requires a new `rng_version` or `objective_version`, and
requires re-preregistration. Retrofitting either randomness or the CI design after kernels exist is the
expensive mistake this document exists to prevent.

Contents: Invariant 1 (keyed randomness) · Invariant 2 (uncertainty) · Invariant 3 (`RaceState`) ·
Invariant 4 (as-of replay) · the primary decision utility.

---

## Invariant 1 — Counter-based keyed randomness

### Why sequential PRNG streams are wrong here

Sharing a seed is *not* sufficient for common random numbers. "Box now" and "stay" diverge, and from the
first divergence they consume different numbers of draws — one pits, meets different traffic, attempts
different passes, retires on a different lap. A sequential stream then delivers different exogenous
values to each option, so the option contrast carries exactly the sampling noise CRN exists to remove.

The fix is a **stateless, addressable** generator: any draw is a pure function of its coordinates, so
"lap-noise for car 4 on lap 31 in replication *i*" is the same value under every option, regardless of
what happened earlier in that option's trajectory.

### Generator

```
rng_version = "philox4x64-10/v1"
```

**Philox4x64-10** — counter-based, crush-resistant, no state, trivially parallel, SIMD-friendly.
4×64-bit counter, 2×64-bit key, 10 rounds, 4×64-bit output per invocation.

Chosen over Philox4x32 for headroom (no field can plausibly overflow) and over a general-purpose hash
because scientific randomness must come from a generator with published statistical testing. **A
general-purpose hash is never used for scientific randomness.**

### Counter and key layout

```
counter (4 × uint64)
  c0 = replication_id                                    full 64 bits
  c1 = (lap_id << 32) | (car_id << 16) | process_id      16/16/16 bits used, top 16 reserved = 0
  c2 = draw_index >> 2                                   see word selection below
  c3 = 0                                                 reserved — nested-game depth (Gate 5)

key (2 × uint64)
  k0 = master_seed
  k1 = scenario_id

word selection
  word = draw_index & 3        one Philox invocation yields 4 words; consecutive draw_index
                               values consume all four before advancing the counter
```

Word selection keeps every draw a pure function of its coordinates while using the whole generator
output — taking only word 0 would discard three quarters of it, which matters at ~10⁸ draws per run.

Field widths and overflow: `lap_id` and `car_id` and `process_id` are each 16 bits and are **checked,
not masked** — an out-of-range value is a programming error and must abort, never silently wrap. `c1`'s
top 16 bits are reserved and must be zero; a non-zero value is an error.

**`scenario_id` identifies the shared random world, never the option.** All options in one decision
board share `scenario_id`. Putting an option index anywhere in the key or counter would destroy CRN and
is the single most likely way to break this invariant by accident.

### `process_id` registry (frozen)

| id | process | `car_id` |
|---:|---|---|
| 0 | reserved / invalid — must abort | — |
| 1 | global Safety Car | `GLOBAL_SENTINEL` |
| 2 | global Virtual Safety Car | `GLOBAL_SENTINEL` |
| 3 | weather transition | `GLOBAL_SENTINEL` |
| 4 | car lap noise | car |
| 5 | pit service time | car |
| 6 | retirement | car |
| 7 | overtake interaction | car (the attacker) |
| 8 | per-car race form | car |
| 9 | joint bootstrap over replication rows | `GLOBAL_SENTINEL` |
| 10 | parameter search (not a race process) | gene index |

```
GLOBAL_SENTINEL = 0xFFFF
```

`8` is drawn **once per replication**, not per lap, and is therefore shared by every option on a board.
It is exogenous: which car has the pace today does not depend on when the focal car stops.

`9` was a hardcoded literal inside `option_board` and absent from this table, so it is registered at
its existing value — naming it changes no interval. Registering anything else at 9 would have collided
silently, which is the argument for the registry being exhaustive rather than illustrative.

`10` is not a race process. It addresses evolutionary-search draws by `(generation, individual, gene)` so
a calibration run replays bit-exactly from `master_seed` alone, independent of core count and evaluation
order. `genetic.mutate_gaussian` cannot be used for this — it draws from `random_float64()`, which is
seeded from the process and cannot be replayed, and a calibration that cannot be reproduced is not
evidence.

Adding a `process_id` is additive and does not change existing streams. Renumbering one does, and
requires a new `rng_version`.

**Note on the zero-argument probe functions.** `rng_version`, `rng_global_sentinel` and `rng_selftest`
were originally justified by a shard-plan requirement for a deterministic zero-argument probe per
module. That tooling (`scripts/generate_mojo_shard_plan.py`, `config/mojo_shard_build_plan_*.json`)
turns out to be **untracked WIP in a separate working tree — not on `origin/main`**, so no such gate is
enforced today. The functions stay regardless: a zero-argument deterministic entry point is real
self-verification surface, and `rng_selftest` in particular fails loudly if the generator, layout or
word selection ever changes. Treat the probe convention as good practice, not a hard requirement.

### Value conversion (frozen, bit-exact)

Given a 64-bit output word `u`:

```
u01_half_open(u) = (u >> 11) * 2^-53          →  [0, 1)     53-bit mantissa, exactly representable
u01_left_open(u) = ((u >> 11) + 1) * 2^-53    →  (0, 1]     never zero — safe for log()
```

### Distributions — every one consumes a **fixed** number of draws

This is load-bearing. Variable-consumption sampling (ziggurat, rejection loops) would make
`draw_index` depend on trajectory, reintroducing exactly the coupling the design removes.

| Distribution | Draws | Definition |
|---|---:|---|
| Uniform `[0,1)` | 1 | `u01_half_open` |
| Bernoulli(p) | 1 | `u01_half_open(u) < p` |
| Exponential(λ) | 1 | `-ln(u01_left_open(u)) / λ` |
| Normal(0,1) | **2** | Box–Muller basic form (below) |

```
z = sqrt(-2 * ln(u01_left_open(u₁))) * cos(2π * u01_half_open(u₂))
```

Box–Muller is chosen over the ziggurat precisely because it consumes exactly two uniforms with no
rejection. Only the **cosine** branch is used; the sine companion is discarded rather than cached,
because caching would make consumption depend on call parity.

`draw_index` advances by the table amount above. A distribution requiring variable draws may not be
added without a new `rng_version`.

### Determinism boundary

Endianness does not enter: Philox is defined over `uint64` arithmetic. Any *serialization* of counters
or keys is little-endian. `rng_version` is part of the configuration hash. Changing the generator,
the layout, the `process_id` numbering, the conversion functions, or any distribution's draw count
creates a **new** `rng_version` — it never silently changes golden results.

### Required test

Run all four options from one decision snapshot to completion. For every `(replication_id, lap_id,
car_id, process_id, draw_index)` tuple **reached by more than one option**, the drawn value must be
identical — including tuples first reached *after* the options diverge. Report the achieved CRN
variance-reduction factor as a first-class benchmark number.

---

## Invariant 2 — Uncertainty computed inside the engine, paired and simultaneous

### Retention

Welford mean/variance cannot support a percentile bootstrap over individual replication outcomes, so
"CIs are free by reusing the replication matrix" and "accumulate with Welford, don't store
trajectories" cannot both hold. Resolution: the engine retains a **compact per-replication record**,
not trajectories:

```
per replication i, per option h:  final_position[i,h]  (uint8)
                                  finished_ahead[i,h]  (bool)
```

At N = 100,000 × 4 options that is well under a megabyte in-process — and would not survive the 1 MiB
SDK boundary, which is why intervals are computed **inside** the engine and only aggregates cross out.

### Resampling is joint across options, never per-option

Each bootstrap draw resamples whole **replication rows** with replacement:

```
draw b:  indices I_b ⊂ {1..N}, |I_b| = N, with replacement
         recompute all four option statistics from the SAME I_b
```

Bootstrapping each option independently would destroy the CRN pairing that the entire randomness design
exists to establish. `B = 1000` resamples (frozen).

### Simultaneous, not marginal

The board *selects* the largest of three contrasts (`box now`, `box+1`, `box+2`, each vs `stay`), so
marginal intervals overstate confidence. Coverage is family-wise over the three contrasts via a
**max-statistic bootstrap**:

```
for each resample b:  T_b = max over h of  |Δ̂_h^(b) − Δ̂_h| / se_h
critical value        t* = the 90th percentile of {T_b}
simultaneous CI       Δ̂_h ± t* · se_h        (family-wise 90%)
```

### Abstention rule (frozen; ε preregistered)

```
Recommend option h only when
  (1) lower simultaneous bound of Δ_h  >  ε          and
  (2) Δ_h − Δ_(next best feasible)     >  margin
Otherwise:  DECISION = INCONCLUSIVE
```

Proposed values, to be frozen at Gate 3C: **ε = 2.0 pp**, **margin = 1.0 pp**, both on
P(ahead of target rival). Rationale: 2 pp is roughly the edge at which acting is defensible, and it sits
an order of magnitude above the N = 100k sampling standard error (~0.16 pp), so the threshold is a
*practical-effect* floor rather than a sampling-noise floor. A statistically positive 0.05 pp
improvement does not justify a pit call.

**The TUI must show `INCONCLUSIVE` as a first-class verdict, not a blank.**

### Labelling

Intervals are labelled **"simulation sampling CI"**. They capture Monte Carlo error only. They do
**not** capture: tyre-degradation or pit-loss parameter uncertainty · race-to-race variation ·
model-form uncertainty · measurement error · regulation-era domain shift. Calibration error is reported
separately from Monte Carlo error and never combined into one number.

---

## Invariant 3 — `RaceState` contract and update order

```
RaceState
  # provenance and as-of watermarks (Invariant 4)
  session_key · corpus_version · event_time_watermark · ingest_sequence_watermark
  source_event_log_hash · state_hash
  last_accepted_source_timestamp[topic] · stale_flags · corrected_field_flags

  # global
  session_clock · lap_number · total_laps · track_regime · weather_state

  # per car
  elapsed_race_time · completed_laps · running_order · interval_to_ahead · gap_to_leader
  compound · tyre_age · stint_index · stint_history · tyre_new_flag
  pit_status · pit_count · in_pit_lane
  retirement_state · penalties*
  estimated_clean_air_pace · estimated_degradation_slope
  tyre_inventory_state
```

\* `penalties` is **text-derived best-effort, not observed** — `RaceControlMessages` carries no
structured penalty field. Excluded from the decision path; a silent parse failure is
indistinguishable from "no penalty".

### Track regime enumeration (from observed `TrackStatus` codes)

```
1 = AllClear      2 = Yellow       4 = SCDeployed
6 = VSCDeployed   7 = VSCEnding
```

Codes 3 and 5 have not been observed and must be logged and surfaced, never silently mapped. Red-flag
handling is unverified and is not in the Monza slice. `Category: SafetyCar` messages in
`RaceControlMessages` carry a `Mode` field and are used as an **independent cross-check** on
`TrackStatus`; disagreement raises a data-quality flag.

### Update order (frozen, exact)

```
1. apply incoming timing event
2. resolve pit entry / exit          (honour _deleted retractions — see below)
3. update lap / stint
4. update track regime
5. update pace estimate
6. recompute running order and gaps
7. set data-quality flags
8. emit an immutable snapshot
```

**Retraction semantics.** Feeds retract records: `PitLaneTimeCollection` emits
`{"PitTimes":{"_deleted":["18"]}}` after having added car 18. Naive accumulation is therefore wrong.
The builder handles `_deleted` **generically for every feed**, not as a special case.

**Ordering tie-break.** Multiple records share one `event_time`, so every record carries a
`source_sequence` and ordering is `(event_time, source_sequence)`. Deterministic replay must never
depend on unspecified ordering among equal timestamps.

**Timestamp precision.** `Utc` fields carry 7 fractional digits (100 ns ticks). Store as an integer
tick count or a string — a naive microsecond datetime parse truncates and loses ordering information.

---

## Invariant 4 — As-of replay and temporal-leakage prohibition

> For a decision snapshot at event time **T**, the state builder may consume only records available at
> or before **T** under the replay's ingest sequence. Post-session corrections, final classifications,
> later compound corrections, future weather observations and retrospective derived tables are
> **scorer-only** and may never enter the feature or decision path.

Consequences, all binding:

1. **Backtests reconstruct every snapshot from the append-only event log**, never from final post-race
   gold tables.
2. **The decision path never queries ClickHouse.** ClickHouse holds corrected and consolidated rows by
   design; querying it would reinstate look-ahead through the storage layer. Enforced architecturally
   by the outbox (the decision runtime holds no DSN, credentials, client dependency or network route).
3. Every snapshot records `event_time_watermark`, `ingest_sequence_watermark`, source hashes, per-topic
   last-accepted timestamp, and stale/corrected flags.

**Required test:** inject a future correction into the archive and assert that an earlier snapshot's
`state_hash` is unchanged. Without this, an excellent-looking backtest can be silently contaminated.

---

## Invariant 5 — Provenance-carrying features and pluggable sources

We hold public timing data. A team that engages may supply their own — full-rate telemetry, tyre
temperatures, state of charge, their own tyre models — or may keep working with theirs while we run
alongside. **Adding a richer source must therefore be a data change, not a code change.** Retrofitting
that means touching every kernel signature, which is why it sits with the invariants.

### Every feature value carries its provenance

The three-class taxonomy is a runtime structure, not a documentation table:

```
FeatureValue
  value        the number
  source       public_timing | team_telemetry | partner_model | inferred | assumed | manual
  data_class   1 observed  |  2 inferred proxy  |  3 assumption-driven
  as_of        event-time watermark (Invariant 4 still applies)
  confidence   optional, source-supplied
```

`data_class` is **derived from `source`**, never set by hand. Two things follow mechanically rather than
by discipline: the model's behaviour, and the claim the output is permitted to support. A board built
from any class-3 input is labelled exploratory in the TUI automatically — nobody has to remember to.

### Channel registry, not hardcoded channels

Public `CarData` carries 5 channels; a team feed may carry ~300. So channel semantics are declarative:

```
channel_id → semantic name · unit · valid range · missing-value convention · source · data_class
```

The `104` staleness rule becomes a per-channel property here rather than logic in the decoder — which
generalises immediately, since a partner feed will have its own missing-value convention (sentinel,
NaN, validity bitmask, per-channel timestamps). Adding channels is a registry entry.

### One event log, N adapters

```
public static archive ─┐
public SignalR live   ─┼→ adapter → canonical typed records + provenance → append-only event log
partner feed (any fmt)─┘                                                          ↓
                                                              ONE as-of RaceState builder
```

Adapters differ; the log, the state builder and the kernels do not. A partner adapter's only job is to
emit canonical records with correct `source` and `as_of`.

### Capability gates: components activate on data class

Each model component declares the features it needs and the **minimum class** it will accept. A thermal
tyre component requiring class-1 tyre temperature simply does not activate on public data; the age-based
model runs instead. Same binary, same kernels, different inputs.

This makes the graceful-degradation property structural: the engine has one code path that works at
every data level, rather than a public build and a team build that drift apart.

### Richer data must still earn its place

The dual-path lesson applies unchanged, and this is the part that is easy to get wrong: **a
higher-class input is not automatically an improvement.** Measured tyre temperature could well degrade
field-level calibration, exactly as the reference paper's learned overtake kernel did. So a new source
enables a component only after a held-out win on the metric that component claims to improve. Plugging
in team data is a hypothesis to be tested, not an upgrade to be assumed.

### Confidentiality follows from the existing deployment shape

If a team supplies data it must never leave their infrastructure. The runtime already satisfies this:
SDK-local execution against a local daemon, control plane unreachable, egress restricted to the timing
host. Their data stays on their box; we ship kernels, not a pipeline into our cloud.

That is also the engagement model. Phase 1: public data proves the engine. Phase 2: they plug their
feed in on their own hardware, and the same kernels get strictly better inputs with nothing rewritten.

---

## The primary decision utility (frozen)

`objective_version = "ahead-of-target-rival/v1"`

The optimizer has exactly **one** primary utility. The TUI may display more; the optimizer may not
choose among them after the fact — that is how a "best" strategy becomes whichever metric flattered the
result.

```
PRIMARY    P(focal car finishes ahead of the named target rival)

SECONDARY  (display and diagnostics only — never optimized against)
           expected finishing position · expected championship points
           P(podium) · P(win) · pit-window downside risk
```

### Frozen resolution rules

| Question | Rule |
|---|---|
| **Target rival** | the nearest **classified** car ahead on track at the decision snapshot |
| **Target retires** | fall back to the next classified car ahead, as of the snapshot at which the retirement became *observable*; the substitution is logged with both identities |
| **DNF ranking** | retired cars placed behind all classified finishers, ordered by completed laps descending, then by retirement time |
| **Penalties** | the simulator predicts **on-road order**. Post-race stewarding is a scorer-side noise channel, reported separately, never fed back into the utility |
| **Ties** | broken by expected finishing position, then expected points |
| **Points vs rival** | the board may *display* a points-optimal option; it may never silently substitute it for the primary utility |

The DNF rule is independently corroborated: Jolpica classifies the Hungarian GP retirements as P20 (55
laps), P21 (48), P22 (13) — laps-completed descending, matching this spec. OpenF1 instead returns
`position: null`, so this rule is what reconciles the two sources.

Any change to the utility or these rules is a new `objective_version` and a new preregistration.

---

## Lap-time model (frozen)

```
l(c, lap) = pace(c) + form(c) + tyre(age(c)) + fuel(lap) + lap_noise + dirty_air(c, lap)
tyre(a)   = delta(c) * a + 1[a > cliff_age] * cliff_slope * (a - cliff_age)
fuel(lap) = + fuel_effect * (laps_remaining - lap)
```

Three points where the sign or the shape is load-bearing, each recorded because getting it wrong was
silent:

* **`fuel` is ADDED.** `laps_remaining - lap` is the fuel still to burn, so a heavy car early is
  slower. Subtracting inverted the profile — the simulated car ran ~3 s/lap quicker at the start than
  at the finish. Common across cars, so it never reordered them; it simply made early laps cheap and
  late laps dear, biasing the early-versus-late pit comparison the board exists to make.
  `degradation_state.load_corrected_rate` REMOVES this term to recover tyre state, so the generator must
  add it or the two kernels disagree on the sign.
* **The tyre CLIFF is not optional.** A fuel-corrected linear slope of ~0.01 s/lap/lap means 25 laps of
  age costs 0.25 s/lap, repaying a ~22.8 s stop only after 91 laps. With the linear term alone the
  board recommends staying out for the whole race in every configuration tested. Corpus,
  fuel-corrected: a knee near age 28-30, post-knee slope of order 0.06-0.16 s/lap/lap.
* **`wear_penalty` has ONE definition** shared by the oracle and the board. The plan requires the
  optimizer to price a stop identically to the simulator; the same applies to what a stop buys, and two
  copies of a piecewise function is how that quietly stops being true.

### Car-to-car interaction (frozen)

A full-field simulation with no coupling between cars is provably no more informative than a
closed-form ranking of its own pace prior: each car's finish time is an independent sum of lap times,
so the finishing order is the order statistic of independent normals, which a softmax computes
directly. Measured as statistically indistinguishable from a one-line grid softmax (DM p = 0.758). The
informative content is the coupling:

```
dirty air / overtaking   a car within dirty_window of the car ahead attempts a pass with
                         sigma(ot_bias + ot_kpace * delta_effective_pace + ot_kage * delta_age);
                         on failure it loses dirty_loss and is held no closer than min_follow.
                         The field is walked LEADER FIRST so the hold cascades into a queue.
safety-car bunching      gaps are COMPRESSED to at most sc_bunch. A pace multiplier alone does the
                         opposite -- it scales every gap up, so the slower car loses proportionally
                         more.
per-car stop laps        jittered per car and per replication, strictly increasing, so undercuts and
                         pit-window traffic occur instead of cancelling.
pit-lane release         a leader that has just entered the pit lane neither dirties the air nor
                         blocks. Without this the follower is held behind a stationary car, which
                         inverts the undercut.
```

Corpus check: real finishing order displaces a mean of **2.68 positions** from the opening lap. A
free-reordering lap-time-sum model churns more, so blocking is what reproduces observed persistence.

### Neutralisations are events with a duration (frozen)

```
per-lap hazard  sc_lambda, vsc_lambda   (events PER LAP, independent of remaining distance)
duration        uniform on 1..sc_dur_max  /  1..vsc_dur_max
SC takes priority; regimes are mutually exclusive; the window is contiguous
```

Corpus over 131 races: SC 1.09 events/race, mean duration 3.17 laps, max 10; VSC 0.47 events/race,
mean 1.28 laps. Two errors are recorded here because both were invisible in aggregate scores:

* A hazard of `lambda / (laps_remaining - lap)` **escalates** from 0.009 on lap 1 to 0.550 on the final
  lap, putting almost every safety car at the end of the race. Dividing by `laps_remaining` instead is
  also wrong: with four laps to run it gives 0.27 per lap, making a safety car 68% likely over that
  stretch and a cheap neutralised stop look attractive with 21 s of unrecoverable pit loss. Incident
  rate is **per lap of racing** and does not rise because the race is nearly over.
* Drawing each lap independently scatters isolated SC laps instead of producing a window — and a
  scattered safety car contains no cheap-pit WINDOW, which is its entire strategic content.

### Estimates already contain what you are about to add (frozen)

Three defects of one shape, each found by measurement rather than review, and each invisible in every
summary statistic:

```
per-car FORM      car_pace measured in-race already contains the car's form, so drawing the pre-race
                  sigma on top double-counts it. Form uncertainty is now the standard error of the pace
                  estimate itself, sigma_lap / sqrt(k), which shrinks as the race is observed.
TYRE PENALTY      car_pace already contains what the CURRENT tyres cost, so adding the absolute
                  wear_penalty(age) charged a car at age 35 about 1.4 s/lap it was already paying. The
                  penalty is INCREMENTAL from the observed state. This also fixes what a stop is worth:
                  resetting age to zero previously returned the car to its WORN-tyre pace, so the model
                  priced the pit loss but not the pace gain that justifies paying it.
LOG POSITION      source_sequence / first_seen_sequence / last_update_sequence are positions in the log,
                  not state. A duplicated frame -- routine on a live reconnect -- renumbers every row
                  after it while changing no content, so including them made the state hash report a
                  change on every reconnect.
```

Hazards must scale with remaining distance. `dnf_prob` was a flat once-per-car probability independent of
`laps_remaining`, so ~9.6% of cars retired whether 57 laps remained or 14; it destroyed cars that were
about to finish and did so hardest late. Now a per-lap hazard compounded over the distance, the same
correction already applied to the safety car.

### Which parameters the objective may choose (frozen)

A calibration search over all 18 dimensions drove `sc_lambda` to **0.000 against its lower bound** — the
objective wanted safety cars abolished. `lap_noise` saturated high and `cliff_age` hit its ceiling in the
same run. That is one coherent preference rather than three quirks: for a PRE-RACE win probability,
real-world structured variance is noise, so a Brier/ECE objective buys calibration by deleting it. The
fitted vector scored **better** on held-out races while describing a world with no safety cars in it.

This is the dual-path hazard the plan names — *a calibration objective rewards whatever correlates with
finishing order* — in its sharpest form, because the reward was real and the physics was wrong. So:

```
MEASURED, pinned      sc_lambda · vsc_lambda · sc_dur_max · vsc_dur_max · slot_spread · dnf_prob
                      Observations from 131 races. The objective gets no vote on them. dnf_prob joined
                      the list after the search drove it to its LOWER bound -- it wanted no retirements
                      at all, the same variance-deletion preference that tried to abolish safety cars.
CONFOUNDED, searched  pace_sigma (reverse causation: a car stuck in traffic records slow "race pace"
                      BECAUSE it finished badly) · cliff_age, cliff_slope (long stints are
                      disproportionately hard-tyre stints on low-degradation circuits)
UNOBSERVABLE, searched  dirty_loss · min_follow · sc_bunch · ot_bias · ot_kpace · ot_kage · lap_noise ·
                      dnf_prob · stop_jitter · hist_weight
```

**A θ selected on the oracle path may never be shipped to the decision board.** Pit timing is largely
*about* neutralisations, so a board configured with `sc_lambda = 0` is worthless however well it scores
on pre-race calibration. Each path is selected on its own metric, and the fitted vector records which
path it belongs to.

Reported per parameter, never inferred from a single best vector: surviving population spread
(identifiability) and bound saturation. A value pinned to a bound is an artifact of the box, not an
estimate — the difference between "the data prefers 0.6" and "0.6 is as far as we let it go".

**But saturation does not automatically mean the bound is wrong.** The feature-weight box was widened
from [-0.60, 1.60] to [-2.00, 3.00], `pace_sigma` from 1.20 to 2.20, and the budget raised to 48x55
because bounds had saturated. The result was WORSE on held-out races — Brier 0.03449 against 0.03034,
BSS +0.303 against +0.387 — with four weights pinned to the NEW bounds and `pace_sigma` driven to 0.000,
deleting per-car form uncertainty entirely. Given a sharper prior and more freedom, the search builds a
near-deterministic configuration that fits the training block and does not transfer.

The box is part of the model, and here it was doing useful regularisation. The narrower one is retained
deliberately. Choosing between them on held-out score is Gate 3B selection, performed before the final
test is opened, and it is recorded here rather than quietly applied.

### The speed claim (rung 2) and what licenses it

```
20 cars x 40 laps x 6,000 replications = 4,800,000 car-lap state updates per arm
  Mojo kernel, through the production socket      0.101 s    47.8M updates/s
  NumPy, fully vectorised over the replication axis  2.821 s     1.7M updates/s
  speedup 28.1x
  max |p_win| divergence between the arms 0.0123
```

The divergence is the licence, not a footnote. At 6,000 replications the Monte Carlo sampling floor on a
win probability is about 0.013, so the two arms agree to within noise and the ratio compares the SAME
computation. `benchmarks/timing/numpy_baseline.py` WITHHOLDS the speed number when they do not: its first
run diverged 0.076 because the NumPy arm lacked the interaction layer, and it refused to report.

The baseline is vectorised over the REPLICATION axis, which is the long, independent one; the car axis is
short and carries the sequential leader-first dependency. A per-replication Python loop would be a
strawman and its ratio meaningless. Both arms pay for the same ten Philox rounds at the same coordinates,
so neither is advantaged by a cheaper generator, and both results are consumed and checked so neither can
be optimised away.

"Faster than Python" remains a category error and is not claimed anywhere.

### The frozen tests were UNDERPOWERED, and the preregistration should have said so

Both frozen tests came out negative and both stand. But the preregistration contained no power analysis,
and it should have — a test that cannot detect the effect it is testing for is not a test.

```
development, 110 races   oracle minus grid_softmax  delta +0.00782  SE 0.00173  4.5 sigma  DM p=0.0000

  scaled to the frozen sample sizes, IF that effect is real:
  2025 frozen             30 races   2.4 sigma   power 76%
  2026 prospective        11 races   1.4 sigma   power 41%
  both combined           41 races   2.8 sigma   power 87%

  races needed for 90% power at this effect size:  46
  races available outside the development seasons: 45
```

So the 2026 run had a **41% chance** of detecting the development effect even if it were entirely real,
and a negative result at that power is weak evidence of absence. The 2025 run at 76% is better but still
not conclusive.

This is a design failure worth naming precisely, because it is not fixable by re-running: 2018 is partial,
2022 is not served by the archive, and 2025 plus 2026 exhaust the unseen data at 45 races — one short of
the 46 needed. **The corpus cannot currently support a 90%-powered frozen test of an effect this size.**

What follows from that, and what does not:

* the frozen results stand and are reported as negative;
* they do NOT license "the simulation beats a grid softmax", which remains unsupported;
* they also do not establish the converse with confidence, and claiming they refute the development
  result would overstate them in the other direction;
* any future preregistration must state the minimum detectable effect at the sample it will have, before
  it is frozen.

### The theta-ensemble: development-validated, and unvalidatable prospectively

The frozen tests both showed the same signature — resolution holding while reliability degraded roughly
tenfold. The model transfers its sharpness and loses its calibration. A post-hoc map fitted on development
cannot fix that, because reliability on development is already 0.0033 and the map would be close to the
identity; the miscalibration only appears out of era.

The real gap is one the plan already names: the intervals cover **sampling error only, not parameter
uncertainty**. A single fitted theta is treated as certain even where `ga_diversity` reports the search
could not resolve it. So the fix propagates the uncertainty the search already measured — K parameter
vectors drawn around the fitted theta, each dimension perturbed by its OWN recorded spread, predictions
averaged. An unidentified dimension widens the prediction; a resolved one barely moves it. The replication
budget is split across members, so compute is held constant and any gain comes from propagating
uncertainty rather than from spending more simulation.

Development, 97 races, identical total compute:

```
ensemble   Brier      REL        RES
0          0.03678    0.00331    0.01426
4          0.03633    0.00293    0.01425
8          0.03612    0.00255    0.01382     <- 23% less miscalibration, resolution held
16         0.03637    0.00323    0.01456     <- 1,000 reps/member lets sampling noise back in
```

**And it cannot be prospectively validated.** The paired Brier effect is +0.00066. Even paired — which
cancels race difficulty, the dominant variance component — reaching 80% power needs **717 races, about 31
seasons**. The ~12 remaining 2026 races give roughly 10% power.

So it is NOT preregistered. A test requiring 717 races is theatre, and running it at 10% power then
reporting the null would be worse than not running it. The ensemble ships behind `--theta-ensemble`,
defaulting to OFF, described as development-validated and nothing more. It may be said to improve
calibration on development seasons at constant compute; it may not be described as validated.

This is also the honest general shape of the problem: F1 produces roughly 23 races a year, so effects
below about 0.002 Brier are permanently beyond prospective proof on public data. Anything smaller has to
be argued from mechanism and development evidence, or not claimed.

### Rung 4 — option-contrast stability, established

This is the rung the power analysis says is reachable. Option contrast compares four options WITHIN one
race under common random numbers, so race difficulty, field strength, circuit and era cancel exactly
rather than statistically, and one race supplies dozens of independent measurements. The same corpus that
cannot resolve a 0.0007 Brier difference resolves an option contrast to a fraction of a point.

45 real decision snapshots, reconstructed through the as-of replay:

```
       N   CI width   predicted 1/sqrt(N)   rec == N=50k   |delta drift|   CRN ratio
   1,000   4.373 pp         4.373 pp             87%          0.267 pp       0.403
   2,000   3.035            3.092                93%          0.199          0.371
   5,000   1.919            1.955                89%          0.126          0.372
  10,000   1.360            1.383                93%          0.090          0.375
  20,000   0.965            0.978                96%          0.039          0.377
  50,000   0.611            0.618               100%          0.000          0.371
```

Three things are established here, and each was a genuine question:

* **the intervals are sampling intervals.** Width tracks 1/sqrt(N) to within 1-2% at every level. Had it
  not, the abstention rule would have been resting on nothing.
* **CRN pairing works, measured rather than assumed.** A variance ratio of 0.37, stable across two orders
  of magnitude of N, is a 2.7x effective replication gain — and it is what makes the contrast resolvable
  where outcome forecasting is not.
* **the operational replication count is 20,000.** That is the smallest N whose recommendation agrees with
  the N=50,000 answer for 95% of snapshots. Below it the board is partly reporting its seed: six of 45
  snapshots recommend something different at N=1,000 than at N=50,000.

The benchmark ladder measured a 1-second budget at N=54,114, comfortably above the 20,000 required, so the
live board can run at an operationally stable replication count inside the feed's roughly 1 Hz cadence.
That is the honest form of the speed claim: not that a board takes nanoseconds, but that the second
between updates is enough to make the recommendation stop depending on the random seed.

One caveat recorded rather than buried: abstention fires on 7% of snapshots at N=1,000 and on none at
operational N, because tighter intervals clear the epsilon bar. The rule is exercised and works, but this
sample contains few genuine near-ties, so the abstention RATE here should not be read as typical.

---

## Configuration hash inputs

Every result carries a `config_hash` over, at minimum:

```
rng_version · objective_version · corpus_version · source_commit
model parameter vector θ · enabled component flags
ε · margin · B · N · bootstrap statistic
metric definitions · exclusions · feed/provider availability per quantity
```
