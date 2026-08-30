---
icon: atom
description: Single-qubit state-vector simulation plus closed-form quantum-computing estimators, propositional/boolean logic and truth tables, fuzzy-set membership and defuzzification, gate-level digital circuit simulation, and a functional-programming combinator library named after category theory.
---

# Quantum computing and formal logic kernels

Seven modules split across two unrelated problem domains that happen to share a page because both
are discrete, symbolic reasoning rather than statistical or numerical modeling. `quantum` and
`quantum_computing` sound like the same subject but are not: `quantum` simulates one qubit (and one
fixed two-qubit Bell pair) as a literal `[a_re, a_im, b_re, b_im]` amplitude vector and applies real
gate matrices to it, while `quantum_computing` never touches a state vector at all — it is a set of
closed-form scalar formulas (fidelity, gate error, surface-code overhead, Grover iteration count,
Shor qubit estimate) that a systems engineer would use to size or budget a quantum computer, taking
already-computed probabilities and error rates as plain `Float64` arguments. The other five modules
are boolean and symbolic math: `boolean_algebra` and `formal_logic` both implement the same set of
two-variable logical connectives (with different function names) but diverge on what else they add —
`boolean_algebra` builds truth tables and evaluates CNF/DNF clause lists; `formal_logic` adds named
inference rules (modus ponens, modus tollens, the two syllogisms) and a full 16-function enumeration
of every possible two-variable boolean function. `fuzzy_logic` is genuine fuzzy-set theory —
membership functions, min/max fuzzy operators, and three defuzzification methods. `logic_circuit` is
gate-level digital design — AND/OR/XOR gates composed into adders, a multiplexer, and a decoder, with
bit-list ↔ integer conversion. `category_theory`, despite its name, is not a formalization of
categories, objects, morphisms, or functors — it is a small functional-programming combinator library
(`map`, `filter`, `fold_left`/`fold_right`, `compose`, `zip_with`, `scan_left`, `take_while`,
`drop_while`, `flat_map`) operating on `List[Float64]` through integer op-codes, borrowing category
theory's vocabulary (the source labels `map_list_fn` a "Functor Map" and `compose` "function
composition") for what the standard library would just call higher-order list functions.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Hadamard on |0>: the equal-superposition state (|0>+|1>)/sqrt(2)
runtime.execute("quantum", "hadamard", [[1.0, 0.0, 0.0, 0.0]])["result"]
# [0.7071067811865476, 0.0, 0.7071067811865476, 0.0]

# Full adder: 1 + 1 + carry-in 1 = 3 = binary 11 -> sum=1, carry_out=1
runtime.execute("logic_circuit", "full_adder", [1, 1, 1])["result"]
# [1, 1]
```

## The modules

| Module | What it does |
| --- | --- |
| `quantum` | Single-qubit state-vector simulation: `qubit_zero`/`qubit_one` basis states, the Hadamard/Pauli-X/Pauli-Z/phase gates, `measure_probability` and `qubit_norm`, a fixed two-qubit Bell state, `expectation_z`, and Bloch-sphere coordinates. |
| `quantum_computing` | Closed-form scalar formulas for quantum-computing systems engineering: measurement probabilities from amplitude-squared inputs, Bell-state fidelity and gate error rate, circuit-depth success probability, surface-code physical-qubit overhead, decoherence (T2/T1) ratio, quantum volume, Grover iteration count, Shor's-algorithm qubit estimate, and an error-correction threshold check. |
| `boolean_algebra` | Two-variable boolean connectives (AND/OR/NOT/XOR/IMPLIES/IFF), 2-variable truth-table generation over a 5-op index space, CNF/DNF clause-list evaluation with negated-literal encoding, tautology and satisfying-assignment counts for that same 5-op space, majority vote, and parity over a `List[Bool]`. |
| `category_theory` | A functional-programming combinator library on `List[Float64]`, selected by integer op-codes: map, filter, left/right fold, two-stage compose, zip-with, prefix scan, take/drop-while, and flat-map. |
| `formal_logic` | Propositional-calculus connectives (the same AND/OR/NOT/XOR/IMPLIES/IFF/NAND/NOR set under different names), four named inference rules (modus ponens, modus tollens, hypothetical and disjunctive syllogism), and tautology/contradiction checks over the full 16-function space of two-variable boolean functions. |
| `fuzzy_logic` | Triangular/trapezoidal/Gaussian membership functions, fuzzy AND/OR/NOT (min/max/complement), three defuzzification methods (centroid, bisector, mean-of-maximum), rule-strength evaluation, and alpha-cut. |
| `logic_circuit` | Gate-level digital logic: the six basic gates, half/full adders, an N-bit ripple-carry adder, a 2:1 multiplexer, a 2-to-4 decoder, and bit-list ↔ integer conversion. |

## `quantum`: one qubit as four real numbers, gates as real matrix multiplies

A qubit `[a_re, a_im, b_re, b_im]` represents `|psi> = a|0> + b|1>` with `a`, `b` complex, stored as
separate real/imaginary parts (`quantum.mojo`'s own docstring states this layout). Every gate is the
textbook 2x2 unitary applied directly to that 4-vector — `hadamard` is exactly `(1/sqrt(2))[[1,1],
[1,-1]]`, `pauli_x` swaps the `|0>`/`|1>` amplitude pairs, `pauli_z` negates the `|1>` pair, and
`phase_gate(q, theta)` multiplies the `|1>` amplitude by `cos(theta) + i*sin(theta)` via real
arithmetic on `(b_re, b_im)`. Starting from `qubit_zero() = [1, 0, 0, 0]`:

```python
plus = runtime.execute("quantum", "hadamard", [[1.0, 0.0, 0.0, 0.0]])["result"]
# [0.7071067811865476, 0.0, 0.7071067811865476, 0.0]  -- the |+> state

runtime.execute("quantum", "measure_probability", [plus])["result"]
# [0.5000000000000001, 0.5000000000000001]  -- equal superposition

runtime.execute("quantum", "bloch_coords", [plus])["result"]
# [1.0000000000000002, 0.0, 0.0]  -- sits on the Bloch sphere's +x axis

runtime.execute("quantum", "expectation_z", [plus])["result"]
# 0.0  -- <Z> = P(0) - P(1), zero for an equal superposition
```

Applying a phase gate with `theta = pi/2` to `|1> = [0, 0, 1, 0]` (an S gate) gives
`[0.0, 0.0, 6.123233995736766e-17, 1.0]` — the `~6e-17` term is `cos(pi/2)` rounding to a hair above
zero rather than exactly zero, and `1.0` is `sin(pi/2)`, so the amplitude becomes `i` as expected.

**`bell_state()` is a fixed 2-qubit reference vector, and the module has no 2-qubit gates.**
`bell_state()` returns the 8-element vector `[1/sqrt(2), 0, 0, 0, 0, 0, 1/sqrt(2), 0]` for
`|Phi+> = (|00> + |11>)/sqrt(2)`, but every other function in this module reads only the first four
elements of whatever `List[Float64]` it is given (guarded by `if len(q) < 4: return empty`, not
`!= 4`). Passing `bell_state()`'s own output to `qubit_norm` reads just `[1/sqrt(2), 0, 0, 0]` — the
`|00>` amplitude pair — and returns `0.5000000000000001`, not `1.0`, because that slice is not a
normalized single-qubit state on its own. There is no `cnot` or other two-qubit gate here; `bell_state`
exists to hand a known entangled reference vector to code outside this module, not to be threaded back
through `quantum`'s single-qubit functions.

## `quantum_computing`: sizing formulas, not a simulator

None of `quantum_computing`'s twelve functions accept a state vector — every argument is a
pre-computed probability, fidelity, error rate, or qubit/depth count, and every function is a single
closed-form expression (`mojo/engine/quantum_computing.mojo`'s own docstring lists all twelve
formulas verbatim). A few worked chains:

| Call | Result | Reading |
| --- | --- | --- |
| `grover_iterations(4.0)` | `1.5707963267948966` | `pi/4 * sqrt(N)` optimal iterations for an unstructured search over 4 items |
| `shor_qubits_needed(2048)` | `4099` | `2n + 3` qubit estimate for factoring an RSA-2048 modulus |
| `logical_qubit_overhead(3)` | `25` | `(2*3-1)^2` physical qubits per logical qubit at surface-code distance 3 |
| `quantum_volume(20, 20)` | `1048576.0` | `2^min(n, d)` for 20 qubits at effective circuit depth 20 |
| `decoherence_time_ratio(100.0, 150.0)` | `1.5` | `T2/T1`; the docstring notes this should stay `<= 2` |
| `circuit_depth_error(0.001, 100.0)` | `0.9047921471137089` | `(1 - single_gate_error)^depth` success probability over 100 gates at 0.1% error each |
| `bell_state_fidelity(0.98)` | `0.9603999999999999` | `overlap^2`, a simplified fidelity |
| `gate_error_rate(0.999)` | `0.0010000000000000009` | `1 - fidelity` |
| `error_correction_threshold(0.001, 0.01)` | `True` | physical error (0.1%) is below the stated threshold (1%) |

`quantum_volume`'s `min(n_qubits, circuit_depth_eff)` means adding more qubits past your effective
circuit depth (or vice versa) does nothing to the reported volume — the smaller of the two numbers is
the entire bottleneck.

## `boolean_algebra` and `formal_logic`: the same connectives, and a same-named function that means two different things

Both modules implement AND/OR/NOT/XOR/IMPLIES/IFF as one-line boolean expressions
(`boolean_algebra.bool_and(a, b)` and `formal_logic.truth_and(a, b)` are both literally `a and b`);
`formal_logic` additionally defines `truth_nand`/`truth_nor`. Where they genuinely diverge:

* `boolean_algebra.truth_table_2(op)` and its `is_tautology_2var`/`count_satisfying_2var` index **5**
  named ops — `0=AND, 1=OR, 2=XOR, 3=IMPLIES, 4=IFF`. Within that 5-op space,
  `count_satisfying_2var` returns `1` (AND), `3` (OR), `2` (XOR), `3` (IMPLIES), `2` (IFF) out of 4
  rows, and `is_tautology_2var` returns `False` for every one of them — none of the five named
  connectives is a tautology, so this function can never observe `True` given only the ops this
  module defines.
* `formal_logic.is_tautology_2var(fn_idx)` and `is_contradiction_2var(fn_idx)` index the full
  **16**-function space of two-variable boolean functions (`fn_idx` 0 through 15, matching the source
  comment's enumeration: `0=contradiction, 1=AND, ..., 13=IMPLIES, 14=NAND, 15=tautology`).
  `is_tautology_2var(15)` is `True` (a hard-coded tautology) and `is_contradiction_2var(0)` is `True`
  (a hard-coded contradiction) — the two functions this module needed to test both exist in-band, at
  fixed indices, which `boolean_algebra`'s narrower 5-op encoding cannot reach at all.
* `formal_logic` also adds `eval_cnf`/`eval_dnf`-style reasoning as four *named inference rules*
  instead of clause lists: `modus_ponens(p, p_implies_q)`, `modus_tollens(not_q, p_implies_q)`,
  `hypothetical_syllogism(p_implies_q, q_implies_r)`, and `disjunctive_syllogism(p_or_q, not_p)`. Read
  the bodies directly and all four reduce to a plain `and` of their two boolean arguments — the value
  they add is entirely in which two propositions the caller is expected to pass in, not in any extra
  arithmetic beyond `truth_and` itself. A caller passing `modus_ponens(True, False)` (premise `p` true
  but `p -> q` false) gets `False` back, which means "this rule did not fire," not "q is false" — the
  same caution applies to all four.
* Only `boolean_algebra` evaluates CNF/DNF clause lists: `eval_cnf(values, clauses)` and
  `eval_dnf(values, clauses)` take a `List[List[Int]]` of literals (a negative index negates that
  variable, 1-indexed) and, for `p=True, q=False, r=True`, `eval_cnf([True, False, True], [[1, 2],
  [-1, 3]])` — `(p OR q) AND (NOT p OR r)` — evaluates to `True`, while `eval_dnf` on `[[1, -2],
  [2, 3]]` — `(p AND NOT q) OR (q AND r)` — also evaluates to `True` via its first clause.
* Only `boolean_algebra` has `majority_vote` and `parity` over an arbitrary-length `List[Bool]`:
  for `[True, True, False, True, False]` (three `True` of five), `majority_vote` returns `True`
  (`3*2 > 5`) and `parity` returns `True` (an odd count of `True` values flips the running XOR an odd
  number of times).

Calling `boolean_algebra.is_tautology_2var(3)` (IMPLIES, `False`) and
`formal_logic.is_tautology_2var(3)` (the projection function "a" — also `False`, but for an unrelated
reason: `a` is neither a tautology nor a contradiction) happen to agree here, but the two functions are
answering different questions from different index spaces; passing a `boolean_algebra`-style op index
into `formal_logic`'s `fn_idx` argument (or vice versa) silently asks about a different function than
intended rather than raising an error.

## `category_theory`: functional-programming combinators, not the mathematical discipline

This is the naming surprise in this batch. `category_theory.mojo`'s own docstring calls it
"Functional programming patterns (Category Theory)," and reading the ten functions confirms that
framing precisely: there are no category, object, morphism, or functor *types* here, no functor laws
verified, no natural transformations — just `List[Float64] -> List[Float64]` (or `-> Float64`)
combinators selected by small integer op-codes, the same shape as a Haskell Prelude reduced to five
unary ops (`0=double, 1=square, 2=negate, 3=increment, 4=abs`) and four binary ones
(`0=add, 1=multiply, 2=max, 3=min`):

```python
data = [1.0, 2.0, 3.0, 4.0, 5.0]

runtime.execute("category_theory", "map_list_fn", [data, 1])["result"]   # op 1 = square
# [1.0, 4.0, 9.0, 16.0, 25.0]

runtime.execute("category_theory", "fold_left", [data, 0.0, 0])["result"]  # op 0 = add, init 0
# 15.0

runtime.execute("category_theory", "compose", [data, 0, 3])["result"]  # double then increment
# [3.0, 5.0, 7.0, 9.0, 11.0]

runtime.execute("category_theory", "scan_left", [data, 0.0, 0])["result"]  # running sum, prefixed with init
# [0.0, 1.0, 3.0, 6.0, 10.0, 15.0]
```

`compose(data, 0, 3)` applying "double" then "increment" to `1.0` gives `2.0 + 1.0 = 3.0` — function
composition in the sense of "apply one thing, then apply another to its result," which is the same
sense the source's "Compose" section comment uses, not composition of morphisms between categorical
objects. Treat the module name as a label borrowed from category theory's vocabulary for these
patterns (map is called a functor, `compose` is called composition), not as a claim that this module
implements category theory itself.

## `fuzzy_logic`: membership, fuzzy operators, and three ways to defuzzify

`gaussian_mf(x, mean, sigma)` is symmetric by construction — `gaussian_mf(25.0, 30.0, 5.0)` and
`gaussian_mf(35.0, 30.0, 5.0)` both return `0.6065306597126334` (`exp(-0.5)`), five units either side
of the mean. A triangular membership function with an asymmetric shape —
`triangular_mf(x, 20.0, 30.0, 50.0)` (rises over 10 units, falls over 20) — sampled at seven points
shows how the three defuzzification methods can disagree:

```python
xs  = [20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0]
mus = [0.0,  0.5,  1.0,  0.75, 0.5,  0.25, 0.0]   # triangular_mf(x, 20, 30, 50) at each x

runtime.execute("fuzzy_logic", "defuzzify_centroid", [xs, mus])["result"]
# 33.333333333333336 -- area-weighted mean, pulled right by the longer 30->50 slope

runtime.execute("fuzzy_logic", "defuzzify_bisector", [xs, mus])["result"]
# 30.0 -- the sample where cumulative membership first reaches half the total (1.5 of 3.0)

runtime.execute("fuzzy_logic", "defuzzify_mom", [xs, mus])["result"]
# 30.0 -- mean of the x values at maximum membership (only x=30 has mu=1.0 here)
```

`centroid` and `bisector`/`mom` genuinely disagree — `centroid` integrates over the whole shape and
is pulled toward the longer, shallower right slope, while `bisector` and `mom` both land exactly on
the peak for this particular (single-mode) shape. `alpha_cut(xs, mus, 0.5)` returns
`[25.0, 30.0, 35.0, 40.0]`, the four sample points whose membership is at least `0.5`. Rule strength
uses the same min/max as the fuzzy operators: `fuzzy_rule_eval([0.8, 0.3, 0.6], 0)` (AND, rule_type 0)
returns `0.3`, the minimum; `fuzzy_rule_eval([0.8, 0.3, 0.6], 1)` (OR) returns `0.8`, the maximum.

**All three defuzzification functions, plus `alpha_cut`, refuse rather than crash on bad input.** If
`x_values` and `memberships` differ in length they return `0.0` (or an empty list for `alpha_cut`)
instead of reading past the shorter list; `defuzzify_centroid`/`bisector`/`mom` additionally scan both
input lists up front and return `0.0` if any value is `NaN` or infinite, so a bad sensor reading never
silently flows into a defuzzified output. `alpha_cut` checks only `x_values` for non-finite entries,
not `memberships` — a `NaN` membership simply fails every `>= alpha` comparison (NaN compares false
against everything under IEEE 754) and is dropped from the result, which happens to produce the same
practical outcome without an explicit guard.

## `logic_circuit`: gates composed into adders, a MUX, and a decoder

Every function here operates on `Int` wires holding `0` or `1`, not `Bool`. The six gates are boolean
functions in disguise (`gate_nand`/`gate_nor` are literally `gate_not(gate_and(...))` /
`gate_not(gate_or(...))`), and every higher-level circuit is built strictly from those six — there is
no separate arithmetic path. Adding `13` and `6` as 5-bit, LSB-first inputs through
`ripple_carry_adder`:

```python
a_bits = runtime.execute("logic_circuit", "int_to_bits", [13, 5])["result"]  # [1, 0, 1, 1, 0]
b_bits = runtime.execute("logic_circuit", "int_to_bits", [6, 5])["result"]   # [0, 1, 1, 0, 0]

runtime.execute("logic_circuit", "ripple_carry_adder", [a_bits, b_bits])["result"]
# [1, 1, 0, 0, 1, 0] -- 5 sum bits (LSB first) + final carry; bits_to_int of the first 5 = 19
```

`13 + 6 = 19`, and the trailing `0` is the carry-out — no overflow at 5 bits. `decoder_2to4(1, 0)`
(`a` is LSB, `b` is MSB) returns `[0, 1, 0, 0]`, activating output index `1 = b*2 + a`.
`multiplexer_2to1(0, 1, sel=1)` selects `b` and returns `1`; the same call with `sel=0` selects `a`
and returns `0`.

**Two guarded edge cases, both intentional per the source's own comments.** `ripple_carry_adder`
returns an empty list — rather than reading `b` past its length — whenever `b` is shorter than `a`;
the comment directly above the check calls out what it prevents: *"A short b would be read past its
end below (uncatchable abort)."* `int_to_bits(value, n_bits)` clamps `n_bits` to a compile-time
`MAX_BIT_WIDTH = 1024` before allocating, so a caller requesting `int_to_bits(5, 10_000)` silently
gets back 1024 bits, not 10,000 — the comment frames this as bounding "the wire-supplied bit width,"
not validating that the request was reasonable.

## Verification

All seven `mojo/tests/libs/test_*.mojo` files behind these modules (`test_quantum.mojo`,
`test_quantum_computing.mojo`, `test_boolean_algebra.mojo`, `test_category_theory.mojo`,
`test_formal_logic.mojo`, `test_fuzzy_logic.mojo`, `test_logic_circuit.mojo`) are auto-generated
coverage smoke tests: each calls every function once with fixed literal arguments (typically `0.5`,
`5`, or a `[0.5, 0.6, 0.7, 0.4, 0.3]`-style fixture list) and checks only that the result is finite or
non-negative-length — none pins a specific numeric or boolean output. Every worked number in this
page was hand-derived from the real formulas in `mojo/engine/quantum.mojo`,
`quantum_computing.mojo`, `boolean_algebra.mojo`, `category_theory.mojo`, `formal_logic.mojo`,
`fuzzy_logic.mojo`, and `logic_circuit.mojo`, and independently re-checked with a plain Python
re-implementation of each formula before being presented here.

**Next:** see [Runtime library catalog](runtime-library-catalog.md) for every module and function, or
[Mixture-of-experts and routing kernels](mixture-of-experts-and-routing-kernels.md) for another family
of modules that share connective-sounding names but diverge in scope the same way `boolean_algebra`
and `formal_logic` do here.
