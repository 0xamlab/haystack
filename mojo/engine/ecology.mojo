"""
ecology.mojo — Ecology & Population Dynamics Library. Zero Python imports.

Provides population growth models, diversity indices, and community similarity
measures for ecological modeling.

Public API:
  logistic_growth              — dN/dt = r*N*(1 - N/K)
  exponential_growth           — N(t) = N0 * exp(r*t)
  carrying_capacity_estimate   — K from logistic model
  lotka_volterra_prey          — dN/dt = r*N - α*N*P
  lotka_volterra_predator      — dP/dt = β*N*P - δ*P
  species_richness_margalef    — D = (S-1) / ln(N)
  shannon_diversity            — H' = -Σ(pi*ln(pi))
  simpson_index                — D = Σ(pi²)
  simpson_diversity            — 1 - D
  jaccard_similarity           — J = shared / (A + B - shared)
  sorensen_similarity          — S = 2*shared / (A + B)
  species_area_relationship    — S = c * A^z
"""
from std.math import log, exp, pow, abs as fabs


# ── logistic_growth ──────────────────────────────────────────────────────────


fn logistic_growth(r: Float64, n: Float64, k: Float64) -> Float64:
    """Logistic growth rate: dN/dt = r*N*(1 - N/K).

    Args:
        r: Intrinsic growth rate.
        n: Current population size.
        k: Carrying capacity.

    Returns:
        Rate of population change.
    """
    if fabs(k) < 1e-30:
        return 0.0
    return r * n * (1.0 - n / k)


# ── exponential_growth ───────────────────────────────────────────────────────


fn exponential_growth(n0: Float64, r: Float64, t: Float64) -> Float64:
    """Exponential growth: N(t) = N0 * exp(r*t).

    Args:
        n0: Initial population size.
        r: Growth rate.
        t: Time elapsed.

    Returns:
        Population at time t.
    """
    return n0 * exp(r * t)


# ── carrying_capacity_estimate ───────────────────────────────────────────────


fn carrying_capacity_estimate(
    n_max: Float64, r: Float64, n0: Float64, t: Float64
) -> Float64:
    """Estimate carrying capacity K from logistic model parameters.

    Uses K = N_max / (1 - (1 - N_max/N0)*exp(-r*t)) rearranged.
    Simplified: K ≈ N_max when population is near equilibrium.
    More precisely: K = n_max (the observed maximum serves as K estimate).

    Args:
        n_max: Maximum observed population.
        r: Growth rate.
        n0: Initial population.
        t: Time elapsed.

    Returns:
        Estimated carrying capacity.
    """
    if fabs(n0) < 1e-30:
        return n_max
    var ratio = n_max / n0
    var denom = 1.0 + (ratio - 1.0) * exp(-r * t)
    if fabs(denom) < 1e-30:
        return n_max
    return n_max * ratio / denom


# ── lotka_volterra_prey ──────────────────────────────────────────────────────


fn lotka_volterra_prey(
    r: Float64, n: Float64, alpha: Float64, p: Float64
) -> Float64:
    """Lotka-Volterra prey equation: dN/dt = r*N - α*N*P.

    Args:
        r: Prey growth rate.
        n: Prey population.
        alpha: Predation rate coefficient.
        p: Predator population.

    Returns:
        Rate of change of prey population.
    """
    return r * n - alpha * n * p


# ── lotka_volterra_predator ──────────────────────────────────────────────────


fn lotka_volterra_predator(
    beta: Float64, n: Float64, p: Float64, delta: Float64
) -> Float64:
    """Lotka-Volterra predator equation: dP/dt = β*N*P - δ*P.

    Args:
        beta: Predator reproduction rate per prey consumed.
        n: Prey population.
        p: Predator population.
        delta: Predator death rate.

    Returns:
        Rate of change of predator population.
    """
    return beta * n * p - delta * p


# ── species_richness_margalef ────────────────────────────────────────────────


fn species_richness_margalef(s: Float64, n: Float64) -> Float64:
    """Margalef's species richness index: D = (S-1) / ln(N).

    Args:
        s: Number of species.
        n: Total number of individuals.

    Returns:
        Margalef diversity index.
    """
    var ln_n = log(n)
    if fabs(ln_n) < 1e-30:
        return 0.0
    return (s - 1.0) / ln_n


# ── shannon_diversity ────────────────────────────────────────────────────────


fn shannon_diversity(proportions_sum_plogp: Float64) -> Float64:
    """Shannon diversity index: H' = -Σ(pi*ln(pi)).

    Pass the pre-computed sum of pi*ln(pi) (which is negative).
    This function negates it to return the positive H'.

    Args:
        proportions_sum_plogp: Pre-computed Σ(pi*ln(pi)).

    Returns:
        Shannon diversity H' (positive value).
    """
    return -proportions_sum_plogp


# ── simpson_index ────────────────────────────────────────────────────────────


fn simpson_index(proportions_sum_p2: Float64) -> Float64:
    """Simpson's concentration index: D = Σ(pi²).

    Args:
        proportions_sum_p2: Pre-computed sum of squared proportions.

    Returns:
        Simpson's index D.
    """
    return proportions_sum_p2


# ── simpson_diversity ────────────────────────────────────────────────────────


fn simpson_diversity(simpson_d: Float64) -> Float64:
    """Simpson's diversity index: 1 - D.

    Args:
        simpson_d: Simpson's concentration index D.

    Returns:
        Simpson's diversity (1 - D).
    """
    return 1.0 - simpson_d


# ── jaccard_similarity ───────────────────────────────────────────────────────


fn jaccard_similarity(
    shared: Float64, total_a: Float64, total_b: Float64
) -> Float64:
    """Jaccard similarity: J = shared / (A + B - shared).

    Args:
        shared: Number of shared species.
        total_a: Total species in community A.
        total_b: Total species in community B.

    Returns:
        Jaccard similarity coefficient [0, 1].
    """
    var denom = total_a + total_b - shared
    if fabs(denom) < 1e-30:
        return 0.0
    return shared / denom


# ── sorensen_similarity ──────────────────────────────────────────────────────


fn sorensen_similarity(
    shared: Float64, total_a: Float64, total_b: Float64
) -> Float64:
    """Sørensen similarity: S = 2*shared / (A + B).

    Args:
        shared: Number of shared species.
        total_a: Total species in community A.
        total_b: Total species in community B.

    Returns:
        Sørensen similarity coefficient [0, 1].
    """
    var denom = total_a + total_b
    if fabs(denom) < 1e-30:
        return 0.0
    return 2.0 * shared / denom


# ── species_area_relationship ────────────────────────────────────────────────


fn species_area_relationship(
    c: Float64, area: Float64, z: Float64
) -> Float64:
    """Species-area relationship: S = c * A^z.

    Args:
        c: Constant (taxon/region dependent).
        area: Area surveyed.
        z: Exponent (typically 0.1-0.5).

    Returns:
        Predicted number of species.
    """
    return c * pow(area, z)
