---
icon: shield-halved
description: Petri net formalism primitives, real differential-privacy mechanisms, model/audit governance scoring, ESG carbon-accounting arithmetic, and the scalar primitives behind a DAG workflow orchestrator -- five unrelated small libraries that happen to share a "keep an AI system accountable" theme.
---

# Governance and workflow kernels

Five kernel modules that do not share a computation, only a purpose: keeping a running system
accountable to something outside its own forward pass. `petri_net` models concurrent systems as
places, tokens and transitions -- the textbook formalism, not a metaphor. `privacy` is a real
differential-privacy library: Laplace and Gaussian noise mechanisms, the exponential mechanism,
randomized response, and the composition theorems that track a privacy budget across queries.
`security_governance` scores prompts, outputs, tenants and audit trails for an LLM-serving
system. `sustainability` is carbon and ESG accounting arithmetic -- GHG scopes, energy and water
intensity, offset cost. `workflow_engine` is the scalar arithmetic underneath a DAG/pipeline
orchestrator: is this node ready, how long should this retry wait, is this step's output shape
still compatible with the next one. None of the five imports another, and none of them appears in
the runtime's capability manifest at all (more on that below) -- they sit together on this page
because nothing else in the corpus documents them, not because they compute related things.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# marking [3, 1], input arcs [1, 0], output arcs [0, 2] -- enough tokens to fire
runtime.execute("petri_net", "fire_transition_2p", [3, 1, 1, 0, 0, 2])["result"]
# 5 -- new marking is [2, 3] (3-1+0, 1-0+2); the function returns the marking's new *sum*

# three ESG pillar scores, weighted equally
runtime.execute("sustainability", "esg_composite_score", [60.0, 70.0, 80.0, 1.0, 1.0, 1.0])["result"]
# 70.0 -- a plain weighted average of E, S and G
```

## The modules

| Module | What it does |
| --- | --- |
| `petri_net` | Petri net formalism: transition enabling/firing, deadlock and liveness checks, place-boundedness, coverability, siphon-emptiness, and incidence, in both fixed-arity (2- or 3-place) and generic list-based forms |
| `privacy` | Differential-privacy mechanisms: Laplace and Gaussian noise addition, the exponential mechanism, randomized response, sequential and advanced composition, and L1/L2 sensitivity |
| `security_governance` | Model-provenance and audit-chain hashing, prompt/output policy scoring, PII sensitivity scoring, tenant quota and RBAC checks, data-retention decay, and a composite governance-compliance score |
| `sustainability` | ESG and carbon-accounting arithmetic: GHG Scope 1/2/3, transport carbon footprint and offset cost, energy/water intensity, waste diversion, renewable-energy fraction, circular-economy index, SROI, and a weighted ESG composite |
| `workflow_engine` | Scalar primitives for a DAG/pipeline orchestrator: node readiness, retry backoff, conditional-branch value, pipeline-stage throughput, completion fraction, timeout remaining, scheduling priority, parallel efficiency, running cost, and schema/type compatibility between chained steps |

## `petri_net`: the textbook formalism, at small fixed sizes

The hint called this "a concurrent-systems modeling formalism," and reading `mojo/engine/petri_net.mojo`
confirms it exactly -- there is no surprise here, only scale. Every function operates on a Petri net
small enough to pass as scalars: a "2-place" function takes the token counts of exactly two places
and the arc weights of one transition; a "3-place" function takes three token counts; the two
`_list` variants (`is_transition_enabled_list`, `fire_transition_list`) generalize to `n_places` via
`List[Int]` arguments instead of named ones, but still model one transition at a time. There is no
struct, no net-wide state, and no `List[List[Int]]` incidence matrix anywhere in the module -- a
caller modeling a real net stitches these primitives together one transition and one place at a
time.

The formalism itself is exactly the standard one. A transition is enabled when every input place
holds at least its arc weight (`is_transition_enabled_2p`: `m0 >= in0 and m1 >= in1`); firing it
subtracts the input weights and adds the output weights (`fire_transition_2p` returns the new
marking's *sum*, `new0 + new1`, not the two new counts separately); a net is deadlocked when no
transition is enabled (`is_deadlocked_1t_2p` is literally `not is_transition_enabled_2p(...)`, and
the 2-transition variant requires *both* to be disabled); coverability checks one place's count
against a target (`marking_val >= target_val`); and a siphon -- a set of places that, once empty,
stays empty forever -- is empty exactly when every place flagged as a member (`s0`/`s1`/`s2`) holds
zero tokens, trivially true if no place is flagged a member at all. All of this is pinned by real
assertions in `tests/mojo/test_wave64.mojo`, not just the auto-generated smoke test:

```python
runtime.execute("petri_net", "is_transition_enabled_2p", [0, 2, 1, 1])["result"]
# False -- marking [0, 2] can't satisfy input arc [1, 1]; place 0 is short one token

runtime.execute("petri_net", "is_live_transition", [5, 10])["result"]
# 0.5 -- enabled in 5 of 10 sampled markings; is_live_transition(0, 0) is defined as 0.0, not NaN

runtime.execute("petri_net", "siphon_empty_3p", [1, 5, 0, True, False, True])["result"]
# False -- place 0 is a siphon member (s0=True) and holds a token, so the siphon isn't empty,
# regardless of place 1's five tokens (s1=False -- not a member, so its count is irrelevant)
```

`incidence_value(output_weight, input_weight)` is the one function that looks unrelated at first
glance but is the same net-effect idea in miniature: `output_weight - input_weight` is exactly the
per-place entry of the incidence matrix a full Petri net analysis would build, computed for a single
(place, transition) pair rather than assembled into a matrix.

## `privacy`: real differential privacy, and the one place randomness enters this whole page

Every function in `mojo/engine/privacy.mojo` is standard differential-privacy machinery, not an
approximation of it. `laplace_mechanism` and `gaussian_mechanism` add noise sampled from the
correctly-calibrated distribution (Laplace via inverse-CDF, Gaussian via Box-Muller with a Taylor-series
cosine the module implements itself rather than importing); `exponential_mechanism_scores` returns
`exp(epsilon * score / (2 * sensitivity))` per candidate -- unnormalized weights the caller must
still normalize or sample from, exactly as its docstring says; `randomized_response` flips a
coin against `p` before deciding whether to report the true Boolean; `composition_epsilon` sums a
list of per-query epsilons (basic sequential composition); `advanced_composition` implements the
tighter theorem, `epsilon * sqrt(2*k*ln(1/delta)) + k*epsilon*(e^epsilon - 1)`; and `sensitivity_l1`/
`sensitivity_l2` both reduce, for the single-record bounded-data case this module targets, to the same
`max(|data_i|)`.

This is also the only module on this page whose output is not a pure function of its
arguments. `laplace_mechanism`, `gaussian_mechanism`, `randomized_response`, `dp_mean`, and
`dp_count` all call `random_float64()` internally, so two identical calls give different answers by
design -- that is the entire point of a noise mechanism. `mojo/tests/libs/test_privacy.mojo` only
checks the outputs are finite, and the real assertions in `tests/mojo/test_wave26.mojo` test the
*shape* of that randomness rather than a fixed value: "`randomized_response(True, 1.0)` is `True` on
every one of 20 calls" (`p=1.0` means zero flip probability), "`dp_count(100, 1.0)` lands within
`[50, 150]`," "at least one of ten `dp_count` calls differs from the true count by more than
`0.001`." The two purely arithmetic functions in the module -- `composition_epsilon` and the
sensitivity pair -- do get exact pinned values instead: `composition_epsilon([0.5, 0.5, 0.5]) ==
1.5`, `sensitivity_l1([1.0, -5.0, 3.0]) == 5.0`.

```python
runtime.execute("privacy", "composition_epsilon", [[0.5, 0.5, 0.5]])["result"]
# 1.5 -- basic composition just sums; pinned exactly in test_wave26.mojo

runtime.execute("privacy", "advanced_composition", [0.5, 0.001, 3])["result"]
# 4.192030945484213 -- strictly greater than the basic-composition total of 1.5 for the same
# k=3 queries at epsilon=0.5; the wave-26 test only asserts "greater than," this is the exact value

runtime.execute("privacy", "exponential_mechanism_scores", [[1.0, 2.0, 5.0], 1.0, 1.0])["result"]
# [1.6487212707001282, 2.718281828459045, 12.182493960703473] -- unnormalized; higher score,
# higher weight, but nothing here sums to 1.0 -- normalizing or sampling is left to the caller
```

## `security_governance`: LLM-serving policy scoring, and a formula it shares with `privacy`

`mojo/engine/security_governance.mojo` scores the operational side of running an LLM service --
provenance, prompt/output policy, tenant isolation, audit trails -- as flat weighted-sum or
threshold arithmetic. Three things are worth flagging explicitly, all found by reading the function
bodies rather than trusting the docstrings alone:

**`tenant_quota_remaining` takes two arguments its own formula never touches.** The signature is
`tenant_quota_remaining(quota_tokens, used_tokens, quota_period_ms, elapsed_ms)`, and the docstring
frames it as "remaining token quota in the current period" -- but the body is exactly
`max(0.0, quota_tokens - used_tokens)`. `quota_period_ms` and `elapsed_ms` are accepted, matching the
"per-period rate limit" framing a caller would expect, but neither one reaches the arithmetic; the
function is a plain clipped subtraction regardless of how much of the period has elapsed. A caller
relying on it to prorate quota against elapsed time gets the same answer at the start of the period
as at the end.

**The module's two 0-1 clipping guards are reachable at very different points.** `prompt_policy_score`'s
weights (`0.4`, `0.4`, `0.2`) sum to exactly `1.0`, so for any input actually confined to `[0, 1]` the
`if score > 1.0: return 1.0` guard can never fire -- `prompt_policy_score(1.0, 1.0, 1.0)` lands on
`1.0` precisely, not above it. `pii_sensitivity_score`'s weights (`0.2`, `0.2`, `0.4`, `0.4`) sum to
`1.2`, so the same guard is live even for in-range inputs: `pii_sensitivity_score(1.0, 1.0, 1.0,
1.0)` computes `1.2` before clipping to `1.0`. Two guard clauses that read identically in isolation
protect against different things in practice.

**`differential_privacy_noise` computes the same sigma `privacy.gaussian_mechanism` uses
internally, but returns it as a number instead of consuming it.** Both modules implement the
identical closed form for the calibrated Gaussian-mechanism standard deviation, `sensitivity *
sqrt(2 * ln(1.25/delta)) / epsilon` -- `security_governance.differential_privacy_noise(1.0, 0.5,
0.01)` returns `6.215022920184479`, and that is exactly the `sigma` that
`privacy.gaussian_mechanism(value, 1.0, 0.5, 0.01)` would compute before sampling
`Normal(0, sigma^2)` and adding it to `value`. The difference is what happens next:
`security_governance`'s version is a pure, deterministic diagnostic -- "how much noise would
(epsilon, delta)-DP require here" -- with a `1e9` sentinel if `epsilon` or `delta` is non-positive,
while `privacy`'s version actually draws the noise and returns a noisy value. A governance dashboard
reporting the DP guarantee in effect calls the first; a query pipeline enforcing it calls the
second.

```python
runtime.execute("security_governance", "tenant_quota_remaining", [1000.0, 400.0, 86400000.0, 1000.0])["result"]
# 600.0 -- 1000 - 400; the 86,400,000 ms period and 1,000 ms elapsed never enter the arithmetic

runtime.execute("security_governance", "differential_privacy_noise", [1.0, 0.5, 0.01])["result"]
# 6.215022920184479 -- the same sigma privacy.gaussian_mechanism would add noise with, computed
# without touching the runtime's random number generator at all
```

`permission_access_check` is a two-stage gate rather than a graceful scale: a time-based
restriction (`time_based_restriction > 0.5`) denies access outright before the role/level comparison
is even evaluated, so a caller with a very high `user_role_level` gets `0.0` during a restricted
window exactly like a caller with none. `audit_log_hash` and `model_provenance_hash` are both
plain rolling hashes built from large odd multipliers (`1000003.0`, `999983.0`, `997.0`) rather than
a cryptographic hash function -- `audit_log_hash` chains forward (`prev_hash * 1000003.0 +
event_type * 997.0 + timestamp + tenant_id`), the same "chain each entry into the last" shape as the
Merkle-adjacent hashing in [Data integrity and encoding](data-integrity-and-encoding.md), but built
from arithmetic rather than a real hash primitive, so it is tamper-evident against accidental
corruption, not against an adversary who can solve for the multiplier.

## `sustainability`: real ESG and carbon-accounting formulas

The hint asked to verify whether this module actually computes carbon/resource-efficiency metrics
rather than something adjacent -- it does, exactly. `mojo/engine/sustainability.mojo` implements the
standard GHG Protocol scope breakdown (`ghg_scope1` is direct emissions, pass-through; `ghg_scope2`
is purchased energy times a grid emissions factor; `ghg_scope3_estimate` is a coarse
revenue-times-intensity-factor proxy for the hard-to-measure value-chain emissions), plus the
intensity ratios (`energy_intensity`, `water_intensity`) and diversion/fraction percentages
(`waste_diversion_rate`, `renewable_energy_fraction`, `circular_economy_index`) that make up a
typical corporate sustainability report, plus `carbon_offset_cost`, `social_return_on_investment`,
and a weighted `esg_composite_score`. Every guard clause is the same shape: divide-by-zero returns
`0.0` rather than `NaN` or `Inf`. All of the following are pinned exactly in
`tests/mojo/test_wave100.mojo`:

```python
runtime.execute("sustainability", "carbon_footprint_transport", [100.0, 0.21])["result"]
# 21.0 -- 100 km at 0.21 kgCO2/km

runtime.execute("sustainability", "ghg_scope2", [10000.0, 0.5])["result"]
# 5000.0 -- 10,000 kWh purchased at a 0.5 kgCO2/kWh grid factor

runtime.execute("sustainability", "esg_composite_score", [80.0, 70.0, 90.0, 0.4, 0.3, 0.3])["result"]
# 80.0 -- (80*0.4 + 70*0.3 + 90*0.3) / (0.4+0.3+0.3); weights need not sum to 1.0, the function
# normalizes by their sum itself
```

## `workflow_engine`: scalar arithmetic for a DAG orchestrator, not the orchestrator itself

`mojo/engine/workflow_engine.mojo` has no scheduler, no graph structure, and no notion of "this
node" beyond the numbers a caller passes in for it -- like the MoE and routing modules documented in
[Mixture-of-experts and routing kernels](mixture-of-experts-and-routing-kernels.md), every function
here is a single checkable formula over plain `Float64` arguments, with the DAG itself assumed to
live entirely on the caller's side. None of the ten functions have pinned wave-suite tests --
`mojo/tests/libs/test_workflow_engine.mojo` is the auto-generated finite-check smoke test only --
so every worked value below was hand-computed independently from the real formulas in the source
file, not copied from an existing assertion.

**`dag_node_ready_score` is a binary gate, not a fractional readiness score.** Despite the name,
there is no partial credit for "8 of 10 dependencies done": the function returns `1.0` only if
`blocked_by_resource <= 0.5` *and* (`n_dependencies <= 0.0` or every dependency has completed), and
`0.0` otherwise. `dag_node_ready_score(3.0, 2.0, 0.0)` (two of three dependencies done, no resource
block) returns `0.0`, identical to `dag_node_ready_score(3.0, 0.0, 0.0)` (zero of three done) --
both "not ready yet."

**`retry_backoff_delay` uses a literal `0.693` in place of `ln(2)`**, so `exp(attempt_number *
0.693)` approximates but is not exactly `2^attempt_number`. At `attempt_number=3.0`,
`base_delay_ms=100.0`, `max_delay_ms=5000.0`, `jitter_factor=0.2`: the uncapped exponential term is
`100 * exp(3 * 0.693) = 799.65` (a whisper under the mathematically exact `100 * 2^3 = 800`), stays
under the `5000` cap, and the final jitter multiply (`* (1 + 0.2 * 0.5)`) brings it to
`879.61`.

**`workflow_completion_fraction` does not clamp to `[0, 1]` and does not guard against
double-counting.** It computes `(completed_nodes - failed_nodes) / total_nodes` directly -- if a
caller's `completed_nodes` count already excludes failures, subtracting `failed_nodes` again
produces a fraction lower than the workflow's real completion rate; the function trusts the caller's
counting convention rather than enforcing one.

```python
runtime.execute("workflow_engine", "dag_node_ready_score", [3.0, 2.0, 0.0])["result"]
# 0.0 -- two of three dependencies isn't "two-thirds ready," it's simply not ready

runtime.execute("workflow_engine", "retry_backoff_delay", [3.0, 100.0, 5000.0, 0.2])["result"]
# 879.6115290911044

runtime.execute("workflow_engine", "chain_output_compatibility", [2.0, 3.0, 5.0, 5.0])["result"]
# 0.36787944117144233 -- type codes match (5.0 == 5.0) but the schema version drifted by one,
# and compatibility decays as exp(-|version_diff|) rather than failing outright or passing silently
```

`chain_output_compatibility` is a hard type gate layered under a soft version decay: a type-code
mismatch zeroes the score outright regardless of how close the schema versions are
(`chain_output_compatibility(2.0, 2.0, 5.0, 7.0) == 0.0`), the same "hard gate, graceful decay only
past it" shape as `model_router.capability_match_score` in the routing family.

## No declared capabilities for any of these five modules

`packages/algenta/algenta/runtime_capability_manifest.json` lists 122 modules with a
`deterministic` / `seed_requirements` / `stateful` capability record per function -- and none of
`petri_net`, `privacy`, `security_governance`, `sustainability`, or `workflow_engine` appear in it
at all. Per [Declared capabilities](capabilities.md), that makes every function in this family
`UNDECLARED` on every axis, not "known to be deterministic." That distinction is not academic for
this page specifically: `privacy`'s five noise-sampling functions genuinely are non-deterministic
and rely on process-global RNG state neither declared nor exposed as a seed argument, and nothing in
the manifest says so -- a caller has to have read this page, or the source, to know that
`laplace_mechanism` and `gaussian_mechanism` behave differently from every other function on it.

**A naming note, not a documentation gap.** `gitbook/operate/privacy-egress.md` documents a
different, unrelated "privacy" surface -- the engine's live egress-policy and PII-redaction
controls, reachable over the admin API. That page and this module share the word "privacy" and
nothing else: `gitbook/operate/privacy-egress.md` is about what a running deployment is allowed to
reach and log; the `privacy` module documented here is differential-privacy math a caller invokes
directly through `runtime.execute`. Neither page's grep of the other's module or endpoint names
turns up a hit.

## Verification

`petri_net` (`tests/mojo/test_wave64.mojo`, 11 test functions covering all 13 module functions),
`privacy` (`tests/mojo/test_wave26.mojo`), and `sustainability` (`tests/mojo/test_wave100.mojo`) all
have real, hand-written pinned-value test suites beyond the per-module `mojo/tests/libs/test_*.mojo`
smoke tests every module in this corpus gets. `security_governance` and `workflow_engine` have only
the auto-generated finite-check smoke test -- every worked number for those two modules in this page
was computed independently from the formulas in `mojo/engine/security_governance.mojo` and
`mojo/engine/workflow_engine.mojo` using the exact same arithmetic the kernel runs, and can be
reproduced by re-running it.

**Next:** see [Mixture-of-experts and routing kernels](mixture-of-experts-and-routing-kernels.md) for
the same "flat scalar formulas, no shared status-code vocabulary" shape applied to a different
family, [Data integrity and encoding](data-integrity-and-encoding.md) for the real hash and Merkle
primitives `audit_log_hash`'s chain shape echoes, or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
