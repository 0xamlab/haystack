---
icon: bullseye
description: Least-squares accuracy on the NIST StRD linear-regression suite, measured in correct digits against the certified values, against fourteen reference arms on the same data.
---

# Least-squares accuracy

Linear least squares is where a numerical library's accuracy is visible. The National Institute
of Standards and Technology publishes a Statistical Reference Dataset suite for exactly this
purpose: eleven linear-regression problems with certified parameter values, several of them
deliberately ill-conditioned to the point where a plain double-precision solver loses most of
its significant digits.

Algenta's least-squares route accepts float64 and returns float64, and carries the
factorisation between those two points at roughly twice that precision. On all eleven datasets
it returns the correctly-rounded exact solution.

**Metric:** NIST's own log relative error, `-log10(|estimate - certified| / |certified|)`, taken
as the minimum over a dataset's parameters. Higher is better. Capped at 15.95, which is the most
a float64 return can express. Certified values are parsed out of the published `.dat` files.

## Results

Correct digits per dataset per arm. `W1`-`W5` are Wampler1-Wampler5. A dash means the arm does
not apply to that model — the polynomial-basis arms fit a single predictor and cannot express
Longley's six-predictor design or the two no-intercept models.

| Arm | Norris | NoInt1 | NoInt2 | Pontius | W1 | W2 | W3 | W4 | W5 | Longley | Filip |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `Polynomial.fit` | 12.09 | - | - | 11.86 | 8.99 | 12.18 | 8.75 | 9.39 | 8.01 | - | 13.84 |
| `Chebyshev.fit` | 12.09 | - | - | 11.62 | 9.48 | 12.05 | 9.20 | 8.89 | 7.81 | - | 12.69 |
| `Legendre.fit` | 12.09 | - | - | 11.77 | 9.28 | 12.41 | 9.07 | 9.08 | 7.64 | - | 12.99 |
| `Hermite.fit` | 12.09 | - | - | 11.62 | 8.45 | 12.03 | 8.42 | 8.37 | 7.67 | - | 12.06 |
| `HermiteE.fit` | 12.09 | - | - | 11.77 | 8.73 | 11.75 | 8.38 | 8.49 | 7.57 | - | 10.19 |
| `Laguerre.fit` | 11.77 | - | - | 11.77 | 5.52 | 9.40 | 5.98 | 4.52 | 2.52 | - | 0.00 |
| `numpy.polyfit` | 12.41 | - | - | 12.28 | 9.03 | 12.68 | 9.02 | 8.11 | 6.13 | - | 8.19 |
| `numpy.linalg.lstsq(rcond=None)` | 12.04 | 14.72 | 15.04 | 7.11 | 9.54 | 10.38 | 9.57 | 8.45 | 6.40 | 10.84 | 0.00 |
| `numpy.linalg.lstsq(rcond=-1)` | 12.04 | 14.72 | 15.04 | 7.11 | 9.54 | 10.38 | 9.57 | 8.45 | 6.40 | 10.84 | 5.90 |
| `numpy.linalg.qr` + `solve_triangular` | 12.28 | 14.72 | 15.12 | 12.39 | 9.57 | 12.81 | 10.10 | 8.42 | 6.42 | 10.95 | 7.35 |
| `scipy.linalg.lstsq(gelsd)` | 12.04 | 14.72 | 15.04 | 7.11 | 9.54 | 10.38 | 9.57 | 8.45 | 6.40 | 10.84 | 5.90 |
| `scipy.linalg.lstsq(gelsy)` | 12.76 | 14.72 | 15.04 | 12.63 | 9.23 | 13.20 | 9.67 | 8.19 | 6.16 | 11.10 | 7.55 |
| `scipy.linalg.lstsq(gelss)` | 12.04 | 14.72 | 15.04 | 7.11 | 9.78 | 10.38 | 9.68 | 8.45 | 6.40 | 10.84 | 5.90 |
| `statsmodels` OLS | 11.97 | 14.72 | 15.12 | 7.11 | 9.54 | 10.38 | 9.50 | 8.41 | 6.42 | 10.84 | 0.00 |
| **Best of field** | **12.76** | **14.72** | **15.12** | **12.63** | **9.78** | **13.20** | **10.10** | **9.39** | **8.01** | **11.10** | **13.84** |
| **Algenta** | **14.06** | **14.72** | **15.34** | **13.51** | **15.95** | **13.20** | **15.95** | **15.95** | **15.95** | **14.62** | **14.01** |
| Digits gained | +1.30 | 0.00 | +0.22 | +0.88 | +6.17 | 0.00 | +5.85 | +6.56 | +7.94 | +3.52 | +0.17 |
| Exact ceiling | 14.06 | 14.72 | 15.34 | 13.51 | 15.95 | 13.20 | 15.95 | 15.95 | 15.95 | 14.62 | 14.01 |

Eight datasets gain digits, three do not, none lose any. The bottom two rows are the result: the
Algenta row equals the exact ceiling on every dataset.

**The exact ceiling is not an estimate.** Each StRD system is solved exactly over
`fractions.Fraction` — every float64 is a dyadic rational, so the design matrix, the normal
equations and the elimination are all exact with no rounding to amplify — and the exact minimiser
is then rounded once to float64 and scored. No float64-returning solver can score above that row,
whatever precision it carries internally, because the limit is the input bits and the return
format. Each ceiling is confirmed independently with `mpmath` at 120 and 200 decimal digits.

Because the Algenta row and the ceiling row are identical, the three datasets with no digits
gained have no headroom left rather than a shortfall: on NoInt1, NoInt2 and Wampler2 the certified
values and the float64 inputs, not the arithmetic, set the number.

### The cap-free version of the same result

Correct digits saturate — at 15.95, and below that at the precision NIST publishes its certified
values to. Distance from the correctly-rounded exact solution does not saturate, and it is the
sharper statement:

| Dataset | Algenta, ulp from exact | Best reference arm | Which arm |
| --- | --- | --- | --- |
| Wampler5 | 0 | 44,171,264 | `Polynomial.fit` |
| Wampler4 | 0 | 3,670,016 | `Polynomial.fit` |
| Wampler1 | 0 | 741,932 | `scipy.linalg.lstsq(gelss)` |
| Wampler3 | 0 | 447,299 | `numpy.linalg.qr` + `solve_triangular` |
| Longley | 0 | 68,073 | `scipy.linalg.lstsq(gelsy)` |
| Pontius | 0 | 1,657 | `scipy.linalg.lstsq(gelsy)` |
| Norris | 0 | 781 | `scipy.linalg.lstsq(gelsy)` |
| Filip | 0 | 122 | `Polynomial.fit` |
| Wampler2 | 0 | 32 | `scipy.linalg.lstsq(gelsy)` |
| NoInt2 | 0 | 2 | `numpy.linalg.qr` + `solve_triangular` |
| NoInt1 | 0 | 0 | `numpy.linalg.lstsq(rcond=-1)` |

Wampler2 shows why this column is worth having. Both routes score 13.20 digits; one of them is
32 ulp from the exact answer and the other is on it. The digit metric cannot resolve that
difference on this dataset, and this table can.

## Where the digits come from

Two levers are separable and the suite separates them, because on this data they do not have the
same effect. `f64 solve` and `dd solve` below are the *same* algorithm — same pivot order, same
reflector sign rule, same inner products by summation — differing only in the arithmetic, so the
gap between the first two columns is attributable to the arithmetic and to nothing else.

| Dataset | f64 solve | dd solve | dd solve, dd basis | centred/scaled basis | normal equations |
| --- | --- | --- | --- | --- | --- |
| Norris | 12.07 | 14.06 | 14.06 | 13.52 | 12.28 |
| NoInt1 | 14.72 | 14.72 | 14.72 | - | 14.72 |
| NoInt2 | 15.52 | 15.34 | 15.34 | - | 15.52 |
| Pontius | 12.01 | 13.51 | 13.51 | 13.22 | 12.21 |
| Wampler1 | 9.33 | 15.95 | 15.95 | 9.99 | 6.47 |
| Wampler2 | 12.70 | 13.20 | 13.20 | 12.75 | 9.40 |
| Wampler3 | 9.05 | 15.95 | 15.95 | 9.99 | 6.47 |
| Wampler4 | 8.25 | 15.95 | 15.95 | 10.14 | 6.47 |
| Wampler5 | 6.23 | 15.95 | 15.95 | 8.53 | 6.47 |
| Longley | 12.87 | 14.62 | 14.62 | - | 7.24 |
| Filip | 7.42 | 7.90 | 14.01 | 14.05 | no result |

Three things this table says that a single headline number would hide.

* **Compensated arithmetic is what carries nine of the eleven datasets.** Wampler5 moves 6.23 to
  15.95 with no change to the design matrix, the pivoting or the method. NoInt1 is unchanged
  because float64 already solves it exactly, and NoInt2 moves the other way for the reason given
  under [Scope](#scope): 15.34 there is the exact answer and 15.52 is an answer two ulp away from
  it that the metric happens to reward.
* **Filip needs the basis too, and the two techniques are antagonistic rather than
  complementary.** On the published power basis Filip is capped at 7.90 digits by the design
  matrix alone — powers of x by repeated float64 multiplication lose the digits before any solver
  runs, and the `dd solve` column reaching exactly 7.90 there is the compensated route sitting on
  that cap. Forming the powers in double-double lifts the cap to 14.01. Centring and scaling the
  domain reaches a comparable 14.05 on Filip, and costs six digits on Wampler1, Wampler3,
  Wampler4 and Wampler5. The published route is the last column of the trio: the power basis,
  formed in double-double.
* **The normal equations are not a viable route on this suite.** The last column is the engine's
  existing `sparse_numerics.factor` least-squares path, re-measured here rather than quoted. It
  forms the Gram matrix, which squares the condition number, and on Filip that leaves the matrix
  numerically not positive definite, so it returns a typed refusal rather than a wrong answer.

### A better design matrix does not rescue a float64 solver

Since the published route forms the power basis in double-double, the obvious question is whether
the reference arms would close the gap given the same better matrix. They were measured that way:
the design matrix built with the powers formed exactly over the rationals and rounded once to
float64 — the best float64 design matrix that exists for these models — handed to every
matrix-consuming arm.

Zero of 79 arm-and-dataset pairs improved. Every pair was unchanged except on Filip, where the
five arms that moved at all got worse, by 0.17 to 0.33 digits. The design matrix is not where
those arms' digits were going.

## Cost

The compensated route against the identical algorithm in plain float64, both in the same process,
back to back, correctness of both asserted before any timing is taken. Twenty repeats per shape.

| Shape | float64 per solve | double-double per solve | Ratio | Repeat spread |
| --- | --- | --- | --- | --- |
| 82 x 11 (Filip's shape) | 20.0 us | 70.8 us | 3.4x - 3.6x | 6% |
| 256 x 16 | 88 us | 414 us | not measured | 104% |
| 1024 x 24 | 643 us | 3.40 ms | not measured | 963% |

**Roughly three and a half times the cost of the float64 route at the shape this suite's hardest
dataset actually has.** That ratio held across all twenty repeats.

The two larger shapes are published with no ratio. Their per-repeat spread is far too wide to be
a property of the code: the load average during these blocks was 232 to 256 on a sixteen-core
machine, and at 8 to 40 repeats a single preemption of either arm moves the ratio further than
the effect being measured. The per-solve times above are the minimum over the twenty repeats,
which is the least-contended sample and therefore an upper bound on each arm's own cost, but
their quotient is not a result and is not offered as one. What the larger shapes do show is the
direction: the overhead is per-flop, while the float64 arm gets progressively more help from the
vector units as the shapes grow, so the ratio rises with size rather than falling.

## Method

* **Metric.** NIST log relative error against the certified values, minimum over a dataset's
  parameters, capped at 15.95. Certified values, data rows and line spans are parsed out of the
  published `.dat` files; nothing is transcribed. The eleven files are byte-identical to the
  copies served by NIST, re-verified on the day of the run.
* **Same bits to every arm.** Every value crosses into the engine as a 16-digit hexadecimal
  IEEE-754 bit pattern, and the two design-matrix constructions are asserted bit-identical before
  any score is computed. A decimal round trip would be *probably* the same bits, which is a
  different claim.
* **Same freedom to every arm.** Arms receive the published predictor columns and the response.
  An arm that builds its own basis from those columns, as the polynomial-series arms do, is free
  to; an arm that consumes a design matrix is handed the standard one, built by repeated float64
  multiplication, and is also measured on the exactly-formed alternative.
* **Interleaved, and asserted deterministic.** Fourteen reference arms run in three passes with a
  rotated order, and every arm's coefficients must come back bit-identical across all three or the
  run fails. Digit numbers are therefore independent of load and of arm ordering.
* **Versions asserted at run time.** numpy 2.5.1, scipy 1.18.0, statsmodels 0.14.6, mpmath 1.3.0,
  Python 3.14.6, with the numpy BLAS and LAPACK backend asserted to be Apple Accelerate. Any
  drift is a hard exit, because a digit measured against a different LAPACK is a different
  measurement.
* **Two code-generation paths.** The engine's numbers are produced under both the just-in-time
  path and a compiled `-O3` binary, and the two are asserted bit-identical. A compiler that
  contracted or reassociated the wrong expression would silently turn every compensated result
  back into a float64 result, and nothing downstream would fail loudly. The arithmetic primitives
  are separately validated at three code-generation levels against exact rational arithmetic,
  with operands crossing in as opaque bit patterns so the compiler cannot fold the arithmetic
  under test.
* **Hardware.** Apple M4 Max, 16 cores, 128 GiB.
* **Load.** Accuracy is load-independent, and this was checked rather than assumed: the full run
  was repeated in a separate session and every coefficient, digit count and ulp distance came
  back identical. The load average was 232 to 256 on a 16-core machine, recorded around every
  block. That is why only one of the three timing shapes is published with a ratio — see
  [Cost](#cost).

## Scope

* **Digits saturate; three datasets have no headroom.** NoInt1 and Wampler2 are exact ties, and
  on NoInt2 the metric has run out of resolution altogether — the exact solution scores 15.34
  there and answers two ulp away from it score 15.52, so the +0.22 in the results table is a
  rounding coincidence and is not offered as accuracy. All three are stated rather than dropped.
  The result rests on the eight datasets where the metric still discriminates.
* **A float64 return cannot exceed about sixteen digits** however good the internals are. On
  Wampler1, Wampler3, Wampler4 and Wampler5 the exact answer is representable and the score is
  the cap.
* **There is no extended-precision escape hatch in the reference field on this hardware.** On
  Apple silicon `numpy.longdouble` is float64, bit for bit, so the reference arms have no wider
  format available to them.
* **`numpy.linalg.lstsq` at its default `rcond=None` scores 0.00 on Filip.** That is rank
  truncation discarding the fit, not a precision loss, and it is reported as measured rather than
  read as a win. The bar on Filip is 13.84, set by `Polynomial.fit`, which conditions the basis.
* **This page measures accuracy.** The cost section is reported for a reader deciding whether to
  use the route, and is not a throughput claim.
* **Eleven datasets are the whole published linear-regression suite.** None was added or removed
  after measuring.

## Reproduce

The eleven datasets are the NIST StRD linear-regression files. The engine side runs from the
repository:

```text title="benchmark"
mojo run benchmarks/mojo_benchmarks/measure_exactnum_strd.mojo <dataset>.spec
```

`benchmarks/external_baselines/strd_lstsq/score.py` runs the fourteen reference arms and computes
every digit column in the same process. `ceilings.py` computes the exact ceilings over the
rationals, `fair_matrix_check.py` runs the better-matrix comparison, and
`benchmarks/mojo_benchmarks/measure_exactnum_lstsq_cost.mojo` produces the cost table.

## See also

* [Benchmarks](overview.md)
* [Compute kernels](compute-kernels.md)
* [Runtime library catalog](../engine/runtime-library-catalog.md)
