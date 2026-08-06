"""test_evolutionary_search.mojo — the evolutionary search over simulation parameters.

The load-bearing tests are REPRODUCIBILITY (the same master_seed must give the same population on any
core count, or a fitted theta is not evidence), BOUNDS (a gene outside its box is a parameter the
simulator was never validated for), ELITISM (fitness must never regress, or the search can lose to its
own starting point), and the two DIAGNOSTICS that decide how much to trust a fitted value — ga_diversity
for identifiability and ga_saturation for whether a value is an estimate or just the edge of the box.
"""
from evolutionary_search import (
    ga_init,
    ga_step,
    ga_best,
    ga_diversity,
    ga_saturation,
    search_version,
    search_selftest,
)


def approx(a: Float64, b: Float64, tol: Float64) -> Bool:
    var d = a - b
    if d < 0.0:
        d = -d
    return d <= tol


def filled(n_dim: Int, v: Float64) -> List[Float64]:
    """A flat bound vector. Nested lists would need an explicit copy at every use site."""
    var out = List[Float64]()
    for _ in range(n_dim):
        out.append(v)
    return out^


def main() raises:
    var failures = 0

    if search_version() != String("evolutionary-search/v1"):
        print("FAIL version", search_version())
        failures += 1

    # ── the selftest must find the peak of -(x-3)^2 on [0,10] ─────────────────
    var st = search_selftest()
    if not approx(st, 3.0, 0.05):
        print("FAIL selftest did not converge to 3.0:", st)
        failures += 1

    var n_dim = 4
    var pop_size = 16
    var lo = filled(n_dim, -1.0)
    var hi = filled(n_dim, 3.0)

    # ── reproducibility: the whole point of keyed randomness ──────────────────
    # If this fails, a fitted theta cannot be replayed and is not reportable evidence. It is also what
    # makes the search independent of core count and evaluation order.
    var p1 = ga_init(lo, hi, pop_size, 4242)
    var p2 = ga_init(lo, hi, pop_size, 4242)
    if len(p1) != pop_size * n_dim:
        print("FAIL ga_init length", len(p1))
        failures += 1
    for i in range(len(p1)):
        if p1[i] != p2[i]:
            print("FAIL ga_init not reproducible at", i)
            failures += 1
            break
    var p3 = ga_init(lo, hi, pop_size, 4243)
    var same = True
    for i in range(len(p1)):
        if p1[i] != p3[i]:
            same = False
            break
    if same:
        print("FAIL a different master_seed produced an identical population")
        failures += 1

    # individual 0 is the midpoint, so the incumbent is always present in generation 0
    for j in range(n_dim):
        if not approx(p1[j], lo[j] + 0.5 * (hi[j] - lo[j]), 1e-12):
            print("FAIL individual 0 is not the box midpoint at gene", j, p1[j])
            failures += 1

    # ── every gene must stay inside its box, through mutation ─────────────────
    var pop = p1.copy()
    var best_seen = -1.0e18
    for g in range(25):
        var fit = List[Float64]()
        for i in range(pop_size):
            # peak at the all-2.0 corner, which sits inside [-1, 3]
            var s = 0.0
            for j in range(n_dim):
                var d = pop[i * n_dim + j] - 2.0
                s -= d * d
            fit.append(s)
        var bi = ga_best(pop, fit, n_dim)
        if len(bi) != n_dim + 1:
            print("FAIL ga_best length", len(bi))
            failures += 1
        # ELITISM: the best fitness must never regress across generations
        if bi[n_dim] < best_seen - 1e-12:
            print("FAIL elitism violated at generation", g, bi[n_dim], "<", best_seen)
            failures += 1
        if bi[n_dim] > best_seen:
            best_seen = bi[n_dim]
        pop = ga_step(pop, fit, lo, hi, 3, 0.5, 0.4, 0.25, 2, 4242, g)
        if len(pop) != pop_size * n_dim:
            print("FAIL ga_step changed the population size", len(pop))
            failures += 1
        for i in range(len(pop)):
            var j = i % n_dim
            if pop[i] < lo[j] or pop[i] > hi[j]:
                print("FAIL gene left its box at generation", g, "index", i, pop[i])
                failures += 1
                break

    # it should have got somewhere near the optimum
    var fit_f = List[Float64]()
    for i in range(pop_size):
        var s = 0.0
        for j in range(n_dim):
            var d = pop[i * n_dim + j] - 2.0
            s -= d * d
        fit_f.append(s)
    var fb = ga_best(pop, fit_f, n_dim)
    if fb[n_dim] < -0.25:
        print("FAIL search did not approach the optimum, best fitness", fb[n_dim])
        failures += 1

    # ── ga_diversity: the identifiability diagnostic ──────────────────────────
    # A converged population must have COLLAPSED spread. If spread stayed wide the objective could not
    # resolve the dimension, and reporting a precise fitted value for it would overstate the evidence.
    var div = ga_diversity(pop, n_dim)
    if len(div) != n_dim:
        print("FAIL ga_diversity length", len(div))
        failures += 1
    for j in range(n_dim):
        if div[j] < 0.0:
            print("FAIL negative spread at", j, div[j])
            failures += 1
    var div0 = ga_diversity(p1, n_dim)
    var collapsed = False
    for j in range(n_dim):
        if div[j] < div0[j]:
            collapsed = True
    if not collapsed:
        print("FAIL spread did not narrow on any dimension after 25 generations")
        failures += 1
    # an identical population has exactly zero spread
    var flat = List[Float64]()
    for _ in range(pop_size):
        for j in range(n_dim):
            flat.append(1.5)
    var divf = ga_diversity(flat, n_dim)
    for j in range(n_dim):
        if not approx(divf[j], 0.0, 1e-12):
            print("FAIL identical population reported nonzero spread", divf[j])
            failures += 1

    # ── ga_saturation: estimate, or just the edge of the box? ─────────────────
    # This is the difference between "the data prefers 0.6" and "0.6 is as far as we let it go", and the
    # calibration run genuinely hit it -- sc_lambda pinned at its lower bound.
    var at_hi = List[Float64]()
    var at_lo = List[Float64]()
    for _ in range(pop_size):
        for j in range(n_dim):
            at_hi.append(hi[j])
            at_lo.append(lo[j])
    var sat_hi = ga_saturation(at_hi, lo, hi)
    var sat_lo = ga_saturation(at_lo, lo, hi)
    var sat_mid = ga_saturation(flat, lo, hi)
    for j in range(n_dim):
        if not approx(sat_hi[j], 1.0, 1e-12):
            print("FAIL saturation at the upper bound should be +1, got", sat_hi[j])
            failures += 1
        if not approx(sat_lo[j], -1.0, 1e-12):
            print("FAIL saturation at the lower bound should be -1, got", sat_lo[j])
            failures += 1
        if not approx(sat_mid[j], 0.0, 1e-12):
            print("FAIL an interior population reported saturation", sat_mid[j])
            failures += 1

    # ── degenerate inputs must not blow up ───────────────────────────────────
    var one = List[Float64]()
    for j in range(n_dim):
        one.append(2.0)
    var d1 = ga_diversity(one, n_dim)
    for j in range(n_dim):
        if d1[j] != 0.0:
            print("FAIL single-individual population reported spread", d1[j])
            failures += 1
    # a zero-width box must stay pinned rather than divide by zero
    var zlo = filled(2, 1.0)
    var zhi = filled(2, 1.0)
    var zpop = ga_init(zlo, zhi, 4, 7)
    for i in range(len(zpop)):
        if zpop[i] != 1.0:
            print("FAIL zero-width box produced", zpop[i])
            failures += 1
    var zfit = List[Float64]()
    for _ in range(4):
        zfit.append(0.0)
    var zstep = ga_step(zpop, zfit, zlo, zhi, 2, 0.5, 1.0, 0.5, 1, 7, 0)
    for i in range(len(zstep)):
        if zstep[i] != 1.0:
            print("FAIL zero-width box drifted under mutation:", zstep[i])
            failures += 1

    if failures == 0:
        print("test_evolutionary_search: PASS")
    else:
        print("test_evolutionary_search: FAILURES =", failures)
        raise Error("test_evolutionary_search failed")
